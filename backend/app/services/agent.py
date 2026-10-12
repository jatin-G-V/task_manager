import json
import logging
import time

from app.services.agent_tools import TOOLS, TOOL_FUNCTIONS
from app.services.groq_client import groq_client
from app.services.timeutil import APP_TZ, now_local


logger = logging.getLogger(__name__)


# The prompt is STATIC on purpose: Groq caches an identical prompt prefix (gpt-oss
# models), which makes every request faster and cheaper. The date and time live in
# a separate message that is added AFTER this prompt, so they never break the cache.
SYSTEM_PROMPT = """You are the assistant inside a personal task-management app. You manage the user's tasks with tools. The CURRENT CONTEXT message gives today's date, the time and the timezone; use it for every relative date or time.

THINK BEFORE YOU ACT
1. What does the user actually want: add, change, finish, delete, look something up, get a suggestion, or just talk?
2. Which tool does that need? Is anything genuinely missing or ambiguous?
3. If the request is clear, act. Do not ask for confirmation of things the user already told you.

ADDING TASKS
- Any message that names something to do ("add read at 7 and eat at 8", "remind me to call Amit tomorrow", "I need to buy milk") -> call add_tasks ONCE, with one entry in items per separate task.
- Never ask "should I add these as separate tasks?" and never add tasks one per turn. Every task in the message goes into the same add_tasks call.
- Put the user's own words in each entry together with its own day or time. If one day or time applies to several tasks ("tomorrow: gym and read"), repeat it in every entry.
- Do not guess am/pm, dates, section, effort or urgency yourself. Pass the wording through; the system resolves it and its reply shows the final time, so the user can correct it.
- add_tasks writes the final reply itself (what was added, any problem, any question). Never add to it or repeat it.
- Ask a question before adding only when you cannot tell WHAT the task is. Keep it to one short question.

SIMILAR OR DUPLICATE TASKS
- These choices apply only when add_tasks says a task is similar to or part of an existing task, not when it says their times overlap.
- add_tasks checks for duplicates itself. If its reply asks the user what to do with a similar existing task, the new task is on hold.
- When the user answers, call resolve_pending. Never call add_tasks again for that task.
    keep it / leave it / no -> keep_existing
    move it / change it / reschedule it -> update_existing
    merge / combine / add it to that -> merge (if the question was about a duplicate, merge means keep_existing)
    add another / anyway / separate / yes add it -> add_separate
- If the answer does not clearly match one of these, ask one short question.

EXACT-TIME CLASHES
- add_tasks may say an exact-time task overlaps another scheduled task. That task is on hold; do not call add_tasks again.
- If the user says to keep the existing task or skip the new one, call resolve_pending with choice=keep_existing.
- If the user explicitly wants both overlapping tasks, call resolve_pending with choice=add_anyway.
- If the user gives a different time, call resolve_pending with choice=reschedule_new and provide new_scheduled_start as an ISO-8601 datetime in the current app timezone. Include new_scheduled_end only when the user gives an end time.
- Never invent a replacement time. If the user says to change the time but gives no time, ask what time they want.

CHANGING, FINISHING AND DELETING
- A clear command with all needed info ("Complete buy milk", "Change buy milk urgency to high") -> call the tool directly.
- When the user names a task, use list_tasks to find its ID. If several tasks match, name them briefly and ask which one. Never guess.
- To act on several tasks at once ("delete all", "complete all my work tasks"), call list_tasks once (limit 100 for "all"), then make ONE complete_task or delete_task call with every ID in task_ids. Never one call per task.
- delete_task ALWAYS needs explicit confirmation first, even for a clear command: name the task titles that will be deleted, wait for a yes, only then call it.
- If a tool returns an error saying a deadline or time is in the past, tell the user plainly and ask for a new time. Never retry with a different time on your own.
- To remove a value (for example "remove the deadline"), use clear_fields in update_task. Never send null.
- If the user changes a task's duration, set only duration; the system keeps the estimated time in sync.
- duration means only a duration the user stated. "In 2 hours" is a deadline, not a 2-hour duration.
- Once you know a task_id, use get_task for its details; do not run list_tasks again.

SUGGESTIONS AND OVERVIEWS
- "What should I do right now" / "what's my top priority" -> recommend_task.
- If the user says how they feel or their energy ("I'm tired", "I have lots of energy") and wants a suggestion -> recommend_for_mood with the matching energy. Never ask about mood or energy yourself and never assume it.
- Each recommended task has a reason: pinned = it is happening now; deadline_risk = the deadline is close, say it needs attention soon; energy_match = it suits how they feel; top_score = the best next pick. Give the reason in one short sentence.
- If the user wants a different suggestion, call the same tool again with exclude_ids set to the ids you already suggested.
- If the list is empty, say nothing is pending right now.
- "What's on my plate today" / "give me my digest" / a general day overview -> daily_digest. If it lists overdue tasks, mention them in one short sentence.
- Never mention how long a task will take unless the user stated a duration.

MESSAGES THAT ARE NOT ABOUT TASKS
- Greetings and small talk: reply briefly and warmly, then steer back to tasks. Call no tool.
- Unrelated questions (general knowledge, coding help, anything outside task management): do not answer them. Politely say you are focused on tasks and ask what they would like to do.

STYLE
- Keep replies short: 1 to 3 sentences for most responses.
- Talk like a helpful assistant texting a friend, not a system printing a log.
- When listing tasks, name them briefly and naturally. Do not dump effort, urgency or deadline for every task unless the user needs it to choose.
- Never show raw task IDs and never use markdown (no **, no backticks, no bullet dashes). Replies render as plain text in a chat bubble.
- After completing an action, confirm it in one sentence. Do not restate every field.
- Give exactly ONE clear reply per turn. Never repeat the same question or statement in different words.
- If a task has a loose time window (has_explicit_time is false), never present the window's start as the task's time. Say "sometime before 4:40 PM" or "sometime tomorrow". Quote a clock time as the task's time only when has_explicit_time is true.
- Never say a task was added, changed or deleted unless the tool call for it ran and succeeded.
"""


MUTATING_TOOLS = {
    "add_tasks",
    "resolve_pending",
    "update_task",
    "complete_task",
    "delete_task",
}

# These tools write the complete reply themselves, so no second LLM call is needed.
QUICK_REPLY_TOOLS = {"add_tasks", "resolve_pending"}


def execute_tool(tool_name: str, args: dict, user_id: str):
    if tool_name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool: {tool_name}")

    return TOOL_FUNCTIONS[tool_name](user_id, args)


def _context_message() -> dict:
    now = now_local()

    return {
        "role": "system",
        "content": (
            "CURRENT CONTEXT\n"
            f"Current date: {now:%Y-%m-%d} ({now:%A})\n"
            f"Current time: {now:%H:%M}\n"
            f"Timezone: {APP_TZ}\n"
            "Use this to resolve relative dates and times (for example \"tomorrow\", "
            "\"next Friday\") the same way the task parser does."
        ),
    }


def run_agent(user_id: str, messages: list) -> tuple[str, bool]:
    started = time.perf_counter()

    # static prompt first (cacheable), then the small dynamic context, then the chat
    convo = [{"role": "system", "content": SYSTEM_PROMPT}, _context_message()]
    convo += messages

    tasks_changed = False
    seen_calls = {}  # per-request cache so an identical mutating call never runs twice
    MAX_STEPS = 9

    for step in range(MAX_STEPS):
        try:
            llm_started = time.perf_counter()

            response = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=convo,
                tools=TOOLS,
                temperature=0.1,
                reasoning_effort="medium",
                parallel_tool_calls=False,
            )

            usage = getattr(response, "usage", None)
            details = getattr(usage, "prompt_tokens_details", None)
            logger.info(
                "AGENT llm step=%d %.2fs prompt_tokens=%s cached_tokens=%s",
                step + 1,
                time.perf_counter() - llm_started,
                getattr(usage, "prompt_tokens", None),
                getattr(details, "cached_tokens", None),
            )

        except Exception:
            logger.exception("Groq call failed")
            return (
                "I couldn't reach the assistant just now — please try again in a moment.",
                tasks_changed,
            )

        msg = response.choices[0].message

        if not msg.tool_calls:
            logger.info("AGENT total=%.2fs steps=%d", time.perf_counter() - started, step + 1)
            return (
                msg.content
                or "Sorry, I didn't catch that — could you rephrase?",
                tasks_changed,
            )

        convo.append(msg.model_dump(exclude_none=True))
        quick = None

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
                logger.info("TOOL %s %s", tc.function.name, args)
                key = (tc.function.name, json.dumps(args, sort_keys=True))

                if tc.function.name in MUTATING_TOOLS and key in seen_calls:
                    result = seen_calls[key]
                else:
                    result = execute_tool(tc.function.name, args, user_id)
                    if tc.function.name in MUTATING_TOOLS:
                        seen_calls[key] = result
                        tasks_changed = True

                if (
                    len(msg.tool_calls) == 1
                    and tc.function.name in QUICK_REPLY_TOOLS
                    and isinstance(result, dict)
                    and result.get("reply")
                ):
                    quick = result["reply"]

            except (ValueError, LookupError) as e:
                result = {"error": str(e)}

            except Exception:
                logger.exception("Tool %s crashed", tc.function.name)
                result = {"error": "That action failed unexpectedly."}

            convo.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

        if quick:
            logger.info("AGENT total=%.2fs steps=%d (quick reply)", time.perf_counter() - started, step + 1)
            return quick, tasks_changed

    return (
        "I got partway through that — check your task list and tell me what's left.",
        tasks_changed,
    )
