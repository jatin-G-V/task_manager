import json
import logging
import re
import time

from app.services.agent_tools import TOOLS as _BASE_TOOLS, TOOL_FUNCTIONS as _BASE_TOOL_FUNCTIONS
from app.services.agent_client import chat, message_to_dict
from app.services.recommend_reply import recommend_for_mood, recommend_task
from app.services.timeutil import APP_TZ, now_local

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Text helpers
# ------------------------------------------------------------

def _plain_text(value: str) -> str:
    """Remove common Markdown syntax before a plain-text chat bubble displays it."""
    text = value or ""
    # fenced code blocks -> keep the inner text
    text = re.sub(r"```(?:[\w+-]+)?\s*([\s\S]*?)```", r"\1", text)
    # links and images -> keep the label
    text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # headings
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    # bullets, numbered lists and block quotes at the start of a line
    text = re.sub(r"^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+|>\s?)", "", text, flags=re.MULTILINE)
    # bold / italic / strikethrough / inline-code markers
    text = re.sub(r"(\*\*|__|~~|`)", "", text)
    text = re.sub(r"(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w)", "", text)
    return text.strip()


def _tidy(value: str, max_sentences: int = 3, max_chars: int = 320) -> str:
    """Keep a conversational reply short: one paragraph, a few sentences."""
    text = _plain_text(value)
    text = re.sub(r"\s*\n+\s*", " ", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    text = " ".join(sentences[:max_sentences]).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


# ------------------------------------------------------------
# respond: how the model talks when no task action is needed
# ------------------------------------------------------------

FALLBACK_RESPONSE = "I'm here. Tell me a task to add, or ask what to work on."

RESPOND_TOOL = {
    "type": "function",
    "function": {
        "name": "respond",
        "description": (
            "Say something to the user WITHOUT changing or reading any task. Use it for "
            "greetings, thanks, acknowledgments such as ok / okay / sure / cool / got it, "
            "complaints or corrections, and for ONE short question when something essential "
            "is missing (for example the user says 'add a task' but not which task). "
            "One or two short, warm sentences in plain text. Never claim in it that a task "
            "was added, changed, completed or deleted."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The short reply to show the user.",
                }
            },
            "required": ["message"],
        },
    },
}


def respond(user_id: str, args: dict) -> dict:
    message = _tidy(args.get("message") or "", max_sentences=3)
    return {"status": "replied", "reply": message or FALLBACK_RESPONSE}


# The two recommendation tools are replaced by versions that also write the reply.
# The schemas are the same dict objects as in agent_tools, so recommend_reply.install()
# (called from main.py) still adds the "another" flag to them.
TOOLS = [*_BASE_TOOLS, RESPOND_TOOL]
TOOL_FUNCTIONS = {
    **_BASE_TOOL_FUNCTIONS,
    "recommend_task": recommend_task,
    "recommend_for_mood": recommend_for_mood,
    "respond": respond,
}

# The prompt is STATIC on purpose: Groq caches an identical prompt prefix (gpt-oss
# models), which makes every request faster and cheaper. The date and time live in
# a separate message that is added AFTER this prompt, so they never break the cache.

SYSTEM_PROMPT = """You are the assistant inside a personal task-management app. You manage the user's tasks with tools. The CURRENT CONTEXT message gives today's date, the time and the timezone; use it for every relative date or time.

THINK BEFORE YOU ACT

1. What does the user actually want: add, change, finish, delete, look something up, get a suggestion, just talk (greeting, thanks, acknowledgment, complaint), or something that is not about their tasks at all (then call decline_request, never answer it)?

2. Which tool does that need? If nothing needs doing, or one essential detail is missing, call respond. Is anything genuinely ambiguous?

3. If the request is clear, act. Do not ask for confirmation of things the user already told you.

WHEN NO ACTION IS NEEDED: USE respond

- respond(message) is how you talk without touching any task. Use it for greetings, thanks, acknowledgments, complaints or corrections, and for ONE short question when something essential is missing.

- Keep the message to one or two short sentences in plain text, in a warm, natural voice. Never claim inside respond that a task was added, changed, completed or deleted.

- Acknowledgments are NOT requests. "ok", "okay", "okayyy", "sure", "suree", "cool", "nice", "alright", "thanks", "got it", "will do" (any spelling or stretched letters) -> respond with a friendly line, for example "Sounds good. Say the word when you want another suggestion or want to add something." Never suggest, complete, update or delete anything because of an acknowledgment.

- If the user asks for the next suggestion in the same breath ("ok next", "sure, something else"), that is a request: recommend again with another=true.

- Complaints or corrections ("I didn't ask for that", "why did you suggest that", "that's wrong") -> respond with a short apology and ask what they would like. Do not explain at length and do not call any other tool.

- "Add a task", "add something", "remind me" with no task named -> respond with one short question asking what the task is (and when, if relevant). Never pass "add a task" itself to add_tasks.

- Exception: if your previous message asked a question that is waiting for an answer (delete confirmation, duplicate, clash, past time, "mark as done?"), a short "yes", "no", "ok" or "skip it" answers THAT question. Use the matching tool, not respond.

ADDING TASKS

- Any message that names something to do ("add read at 7 and eat at 8", "remind me to call Amit tomorrow", "I need to buy milk") -> call add_tasks ONCE, with one entry in items per separate task.

- Never ask "should I add these as separate tasks?" and never add tasks one per turn. Every task in the message goes into the same add_tasks call.

- Put the user's own words in each entry together with its own day or time. If one day or time applies to several tasks ("tomorrow: gym and read"), repeat it in every entry.

- Do not guess am/pm, dates, section, effort or urgency yourself. Pass the wording through; the system resolves it and its reply shows the final time, so the user can correct it.

- add_tasks writes the final reply itself (what was added, any problem, any question). Never add to it or repeat it.

- If you cannot tell WHAT the task is, use respond to ask one short question instead of calling add_tasks.

SIMILAR OR DUPLICATE TASKS

- These choices apply only when add_tasks says a task is similar to or part of an existing task, not when it says their times overlap.

- add_tasks checks for duplicates itself. If its reply asks the user what to do with a similar existing task, the new task is on hold.

- When the user answers, call resolve_pending. Never call add_tasks again for that task.

- This pending resolution takes precedence over the general ADDING TASKS rule: interpret the user's reply in the context of the question you just asked. For "skip it", "don't add it", "cancel", or equivalent, call resolve_pending with choice=keep_existing; do not call add_tasks. For a part-of question, this skips only the new task and leaves the existing task unchanged.

    keep it / leave it / no / do nothing / skip it / don't add it -> keep_existing (for a part-of question this skips the new task and leaves the existing task unchanged)

    move it / change it / reschedule it -> update_existing

    merge / combine / add it to that -> merge (if the question was about a duplicate, merge means keep_existing)

    add another / anyway / separate / yes add it -> add_separate

- If the answer does not clearly match one of these, use respond to ask one short question.

EXACT-TIME CLASHES

- add_tasks may say an exact-time task overlaps another scheduled task. That task is on hold; do not call add_tasks again.

- If the user says to keep the existing task or skip the new one, call resolve_pending with choice=keep_existing.

- If the user explicitly wants both overlapping tasks, call resolve_pending with choice=add_anyway.

- If the user gives a different time, call resolve_pending with choice=reschedule_new and provide new_scheduled_start as an ISO-8601 datetime in the current app timezone. Include new_scheduled_end only when the user gives an end time.

- Never invent a replacement time. If the user says to change the time but gives no time, ask what time they want.

- If the user wants to move or shift the EXISTING task to make room, call update_task once on that existing task (find its ID with list_tasks; for "shift by N minutes" use shift_minutes, do not calculate the time yourself). The system then adds the held task automatically when the clash is gone, or asks again with the new times. Never call add_tasks again for the held task and never repeat the move.

- If add_tasks says the requested time has already passed, the task is held for a time correction. When the user gives a future replacement, call resolve_pending with choice=reschedule_new and provide new_scheduled_start (or new_deadline for a flexible task). If they decline, call resolve_pending with choice=cancel. Do not repeat the old duplicate question or call add_tasks again.

CHANGING, FINISHING AND DELETING

- A clear command with all needed info ("Complete buy milk", "Change buy milk urgency to high") -> call the tool directly.

- Only call complete_task when the user clearly says a task is done, finished or completed, or asks you to mark it. A suggestion you made is never a reason to complete anything.

- When the user names a task, call list_tasks first to find its ID, then use that ID. Never put a task title or any guessed text in task_id or task_ids. If several tasks match, name them briefly and ask which one. Never guess.

- To act on several tasks at once ("delete all", "complete all my work tasks"), call list_tasks once (limit 100 for "all"), then make ONE complete_task or delete_task call with every ID in task_ids. Never one call per task.

- For a bulk update with the same changes, call update_task once with every matching ID in task_ids.

- For "all overdue tasks", call list_tasks with limit=100, select only tasks whose is_overdue field is true, then update that set. Do not include completed tasks or tasks that are merely due later today.

- Enforce deletion through the tool: first call delete_task with confirmation=request. It returns the exact titles and asks the user to confirm; do not claim deletion. On yes, call again with confirmation=confirm (include the same IDs if available). On no, call with confirmation=cancel. The code refuses to delete without a matching confirmation.

- If an update would overlap another exact-time task, explain the task names and local times from the tool result. Ask whether to keep the current times, apply the changes anyway, or use different times. For an accepted overlap call resolve_pending with update_anyway. If the user supplies replacement times, call update_task again with those times.

- If the user says a task has a deadline, update it as a flexible task with deadline; do not turn the deadline into a scheduled start time.

- If a tool returns an error saying a deadline or time is in the past, tell the user plainly and ask for a new time. Never retry with a different time on your own.

- To remove a value (for example "remove the deadline"), use clear_fields in update_task. Never send null.

- If the user changes a task's duration, set only duration; the system keeps the estimated time in sync.

- duration means only a duration the user stated. "In 2 hours" is a deadline, not a 2-hour duration.

- Keep start times and deadlines distinct: "start/begin in 90 minutes" means a scheduled start; "finish/complete by/in 90 minutes" means a deadline. If the wording does not say whether the time is for starting or finishing and that distinction changes the task, ask one brief clarification rather than guessing.

- Once you know a task_id, use get_task for its details; do not run list_tasks again.

SUGGESTIONS AND OVERVIEWS

- "What should I do right now" / "what's my top priority" -> recommend_task.

- If the user says how they feel or their energy ("I'm tired", "I have lots of energy") and wants a suggestion -> recommend_for_mood with the matching energy. Never ask about mood or energy yourself and never assume it.

- The recommendation tools write the final reply themselves. Never add to it or repeat it.

- If the user asks for a different suggestion ("something else", "anything else", "another one", "what else", "next"), call the SAME recommendation tool again with another=true. The system remembers what was already shown. Never invent ids and never use list_tasks for this.

- A suggestion is only a suggestion. It never changes, completes or deletes any task. Only suggest when the user asks for a suggestion.

- "What's on my plate today" / "give me my digest" / a general day overview -> daily_digest. If it lists overdue tasks, mention them in one short sentence.

- Never mention how long a task will take unless the user stated a duration.

MESSAGES THAT ARE NOT ABOUT TASKS

- Greetings and small talk ("hi", "thanks"): call respond with a warm line that invites them to continue (for example, "Hi! What should we work on?"). Do not invent the user's name.

- General knowledge or trivia ("what is the capital of France?"), maths, coding help, writing, translation, news, or advice unrelated to the user's tasks: NEVER answer it, not even in one short line. Call decline_request with kind=off_topic.

- Features this app does not have: setting reminders, alarms or notification settings, calendar sync ("set a reminder 10 minutes before my meetings", "notify me before events", "wake me up at 6"). Do NOT add a task for it. Call decline_request with kind=unsupported_feature.

- A reminder about one specific thing is just a normal task: "remind me to call Amit tomorrow at 4" -> add_tasks with "call Amit tomorrow at 4".

- If one message mixes a task with an unrelated question, handle only the task part and ignore the rest.

STYLE

- Keep replies short: 1 to 3 sentences for most responses.

- Talk like a helpful assistant texting a friend, not a system printing a log.

- Avoid filler praise and exaggerated encouragement; state the useful recommendation directly.

- When listing tasks, name them briefly and naturally. Do not dump effort, urgency or deadline for every task unless the user needs it to choose.

- Never show raw task IDs and never use markdown (no **, no backticks, no bullet dashes). Replies render as plain text in a chat bubble.

- After completing an action, confirm it in one sentence. Do not restate every field.

- Give exactly ONE clear reply per turn. Never repeat the same question or statement in different words.

- If a task has a loose time window (has_explicit_time is false), never present the window's start as the task's time. Say "sometime before 4:40 PM" or "sometime tomorrow". Quote a clock time as the task's time only when has_explicit_time is true.

- Never say a task was added, changed or deleted unless the tool call for it ran and succeeded.

- Do not claim that the schedule is clear or non-conflicting unless a tool result explicitly checked the complete set being discussed. Never contradict an overlap result.

- Times and dates returned by tools are already formatted in the app's local timezone. Use those phrases as written; never reinterpret them or explain them as UTC, a sync delay, or a display format.

"""

MUTATING_TOOLS = {
    "add_tasks",
    "resolve_pending",
    "update_task",
    "complete_task",
    "delete_task",
}

# These tools write the complete reply themselves, so no second LLM call is needed.
QUICK_REPLY_TOOLS = {
    "add_tasks",
    "resolve_pending",
    "update_task",
    "delete_task",
    "decline_request",
    "recommend_task",
    "recommend_for_mood",
    "respond",
}

# Errors that are already written for the user. Returning them directly avoids a
# slow extra model step (and a retry loop where the model keeps guessing times).
USER_FACING_ERROR_TOOLS = {"update_task", "resolve_pending", "complete_task"}

# ------------------------------------------------------------
# "Add a task for me": nothing to add yet. The model should ask via respond;
# if it still sends this to add_tasks, replace the raw error with a helpful question.
# ------------------------------------------------------------
NOT_A_TASK_REPLY = (
    "What task would you like to add? Tell me what it is and when, "
    "for example \u201cCall Amit tomorrow at 4 PM\u201d."
)


def _is_not_a_task(reply: str) -> bool:
    return (
        reply.startswith("I couldn't add")
        and reply.endswith("That doesn't look like a task.")
        and "\n" not in reply
    )


# ------------------------------------------------------------
# Guard for the one action that must never happen by accident.
# The model decides what the user means; this only checks that the user
# actually talked about finishing something before a task is completed.
# ------------------------------------------------------------
CONFIRM_COMPLETE_MARKER = "mark that task as done"
CONFIRM_COMPLETE = (
    "Do you want me to mark that task as done? Reply “yes” to confirm, "
    "or tell me which task you finished."
)
_COMPLETE_WORDS = re.compile(
    r"\b(done|complete|completed|completes|finish|finished|finishing|mark|tick|ticked|"
    r"did|crossed? off|check(?:ed)? off|ho gaya|hogaya|kar liya|khatam)\b",
    re.IGNORECASE,
)
_YES = re.compile(
    r"^\s*(yes|yeah|yep|yup|y|ok|okay|sure|please do|do it|go ahead|haan|ha)\b",
    re.IGNORECASE,
)


def _text(message) -> str:
    content = message.get("content") if isinstance(message, dict) else ""
    return content if isinstance(content, str) else str(content or "")


def _completion_allowed(messages: list) -> bool:
    last_user_index = -1
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], dict) and messages[index].get("role") == "user":
            last_user_index = index
            break
    if last_user_index < 0:
        return False

    last_user = _text(messages[last_user_index])
    if _COMPLETE_WORDS.search(last_user):
        return True

    # the user answered "yes" to our own "mark as done?" question
    for index in range(last_user_index - 1, -1, -1):
        message = messages[index]
        if isinstance(message, dict) and message.get("role") == "assistant":
            return CONFIRM_COMPLETE_MARKER in _text(message) and bool(_YES.match(last_user))
    return False


def _is_user_facing_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "in the past" in lowered
        or "already ended" in lowered
        or "more than one matching task" in lowered
    )


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

    completion_allowed = _completion_allowed(messages)

    tasks_changed = False
    seen_calls = {}  # per-request cache so an identical mutating call never runs twice
    MAX_STEPS = 9

    for step in range(MAX_STEPS):
        try:
            llm_started = time.perf_counter()
            response, provider = chat(convo, TOOLS)
            usage = getattr(response, "usage", None)
            details = getattr(usage, "prompt_tokens_details", None)
            logger.info(
                "AGENT llm step=%d provider=%s %.2fs prompt_tokens=%s cached_tokens=%s",
                step + 1,
                provider,
                time.perf_counter() - llm_started,
                getattr(usage, "prompt_tokens", None),
                getattr(details, "cached_tokens", None),
            )
        except Exception:
            logger.exception("LLM call failed")
            return (
                "I couldn't reach the assistant just now — please try again in a moment.",
                tasks_changed,
            )

        msg = response.choices[0].message

        if not msg.tool_calls:
            logger.info("AGENT total=%.2fs steps=%d", time.perf_counter() - started, step + 1)
            text = _plain_text(msg.content)
            if step == 0:
                # a purely conversational reply (no tool ran): keep it short
                text = _tidy(text, max_sentences=4, max_chars=420)
            return (
                text or "Sorry, I didn't catch that — could you rephrase?",
                tasks_changed,
            )

        convo.append(message_to_dict(msg))

        quick = None

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
                logger.info("TOOL call name=%s", tc.function.name)

                if tc.function.name == "complete_task" and not completion_allowed:
                    # The user did not say anything about finishing a task.
                    logger.warning("GUARD complete_task blocked: the user did not ask to complete")
                    result = {"status": "needs_confirmation", "reply": CONFIRM_COMPLETE}
                    if len(msg.tool_calls) == 1:
                        quick = CONFIRM_COMPLETE
                else:
                    key = (tc.function.name, json.dumps(args, sort_keys=True))

                    if tc.function.name in MUTATING_TOOLS and key in seen_calls:
                        result = seen_calls[key]
                        logger.info("TOOL replay_cached name=%s", tc.function.name)
                    else:
                        result = execute_tool(tc.function.name, args, user_id)

                        if tc.function.name in MUTATING_TOOLS:
                            seen_calls[key] = result

                            if tc.function.name == "delete_task":
                                tasks_changed = result.get("status") == "deleted"
                            elif tc.function.name == "update_task" and isinstance(result, dict):
                                tasks_changed = tasks_changed or result.get("status") != "needs_decision"
                            else:
                                tasks_changed = True

                    if (
                        len(msg.tool_calls) == 1
                        and tc.function.name in QUICK_REPLY_TOOLS
                        and isinstance(result, dict)
                        and result.get("reply")
                    ):
                        quick = result["reply"]
                        if tc.function.name == "add_tasks" and _is_not_a_task(quick):
                            quick = NOT_A_TASK_REPLY
                    elif (
                        len(msg.tool_calls) == 1
                        and tc.function.name in {"recommend_task", "recommend_for_mood"}
                        and not result
                    ):
                        quick = "Nothing needs attention right now."

            except (ValueError, LookupError) as e:
                result = {"error": str(e)}
                # Past-time and ambiguity errors are already user-ready. Reply
                # immediately instead of letting the model retry with new guesses.
                if (
                    len(msg.tool_calls) == 1
                    and tc.function.name in USER_FACING_ERROR_TOOLS
                    and _is_user_facing_error(str(e))
                ):
                    quick = str(e)
            except Exception:
                logger.exception("Tool %s crashed", tc.function.name)
                result = {"error": "That action failed unexpectedly."}

            outcome = (
                "error" if isinstance(result, dict) and result.get("error")
                else result.get("status", "ok") if isinstance(result, dict)
                else "ok"
            )
            item_count = len(result) if isinstance(result, (list, tuple)) else None
            logger.info(
                "TOOL done name=%s outcome=%s items=%s",
                tc.function.name,
                outcome,
                item_count,
            )

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