import json
from datetime import datetime
from typing import Optional, Literal
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
from pydantic import BaseModel, ValidationError

from app.services.groq_client import groq_client



class ParsedTask(BaseModel):
    title: Optional[str] = None
    section: Optional[Literal["work", "personal", "leisure"]] = None
    is_task: bool = True
    brief: Optional[str] = None

    schedule_type: Optional[Literal["flexible", "scheduled"]] = None
    deadline: Optional[str] = None
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None
    has_explicit_time: Optional[bool] = None

    is_recurring: Optional[bool] = False
    recurrence: Optional[str] = None
    recurrence_end: Optional[str] = None

    # Duration explicitly stated by the user. Never infer this field.
    duration: Optional[int] = None

    # Final expected time required to complete the task.
    # Explicit duration takes priority; otherwise the AI estimates it.
    estimated_time_minutes: Optional[int] = None

    effort: Optional[Literal["low", "medium", "high"]] = None
    urgency: Optional[Literal["low", "medium", "high", "urgent"]] = None

SYSTEM_PROMPT = """
You are an AI task parser for a personal task-management application.

Convert the user's input into structured task information.

Use the meaning of the complete input, not isolated keywords.

Current date: {today} ({weekday})
Current time: {current_time}

IMPORTANT ABOUT EXAMPLES: Every date, weekday and time used inside the
examples below is FICTIONAL. The examples pretend that the current moment
is Wednesday, 2031-03-12 13:00. Never copy any date from an example into
your answer. Always calculate dates from the real current date and time
given above.

--------------------------------------------------
1. TASK vs NON-TASK
--------------------------------------------------

Determine whether the input represents a task.

If it is NOT a task:
- is_task = false
- all other fields = null

Do not invent a task from conversational statements.

A bare topic or noun phrase that could plausibly become a task is still a task.

Examples:
- "Mumbai trip" -> task
- "Website redesign" -> task
- "Client presentation" -> task

For a bare topic:
- is_task = true
- extract only information genuinely supported by the input
- provide a title
- provide a section when the topic clearly indicates one
- do not invent scheduling, deadlines, effort, urgency, duration, or other
  unsupported information
- schedule_type = null, has_explicit_time = null (there is no time
  information at all, so this is unknown, NOT false)

If there is no reasonable basis for a field, return null.

Reserve is_task = false for input that is not attempting to name a task, such as:
- feelings
- opinions
- greetings
- small talk
- questions about what the assistant can do


--------------------------------------------------
2. BASIC INFORMATION
--------------------------------------------------

SECTION

work: job, university, meetings, clients, professional responsibilities
personal: errands, shopping, travel, household tasks, personal responsibilities
leisure: entertainment, hobbies, relaxation, recreation

Use the meaning of the complete input.

TITLE

Create a concise title that represents the actual task.

BRIEF

The brief is optional and is null by default. Write a brief ONLY when the
user's input contains meaningful extra information that is NOT already
captured in the title or in any other field.

Rules:
1. The brief must add new information. If it would only restate or
   rephrase the title, return null.
2. Never put timing information in the brief: no deadline, date, time,
   duration, recurrence, or schedule. These already live in their own
   fields. A brief such as "Expected to last about 45 minutes" or
   "Purchase milk after work tomorrow" is WRONG.
3. Never invent a reason, purpose, goal, mood, or benefit. Do not add
   phrases such as "to relax", "to stay healthy", "to impress the client"
   unless the user said it.
4. Never invent facts, people, places, requirements, actions, or context
   that are not supported by the user's input.
5. Use the user's own details only: what to check, what to include, what
   to verify, who or what is involved, special conditions.
6. Keep it to one short sentence.
7. Personal and leisure tasks normally have brief = null unless the user
   gave real additional detail.

Examples:

"Buy milk tomorrow" -> brief = null
"Meeting with Amit tomorrow at 3 PM for 45 minutes" -> brief = null
"Watch Interstellar tonight" -> brief = null
"Call Amit to discuss the deployment issue" -> brief = "Discuss the deployment issue"
"Submit final report Friday, verify all numbers first" -> brief = "Verify all numbers before submission"
"Plan Mumbai trip, check hotels, transport and places to visit" -> brief = "Check hotels, transport and places to visit"


--------------------------------------------------
3. RESOLVING DATES AND TIMES
--------------------------------------------------

Always resolve relative expressions using the current date and time
provided at the top. Never use dates from examples as the current date.

"in 2 hours" / "in 30 minutes" -> current datetime + that duration
"tomorrow" -> tomorrow's calendar day
"this week" -> the current calendar week (Monday to Sunday)
"next week" -> the following calendar week (Monday to Sunday)
"this month" -> the current calendar month
"next month" -> the following calendar month
"end of the month" -> 23:59:59 on the last day of the current month
"end of next month" -> 23:59:59 on the last day of the following month

WEEKDAY NAMES (Monday to Sunday)

Weeks always run Monday to Sunday.

"Friday" / "this Friday" -> the upcoming Friday within the current
   calendar week. If today is that weekday, use today if the time has not
   passed; otherwise use the next occurrence.
   If that weekday has already passed in the current calendar week, use
   the next occurrence of it.
"next Friday" -> the Friday of the FOLLOWING calendar week (the week that
   starts on the next Monday). It is never the Friday of the current week.
   The same rule applies to every weekday: "next Monday", "next Tuesday",
   and so on always mean that weekday in the following calendar week.

Example (pretend today is Wednesday 2031-03-12):
"Friday" / "this Friday" -> 2031-03-14
"next Friday" -> 2031-03-21
"next Monday" -> 2031-03-17
"Wednesday" -> 2031-03-12 if the time has not passed, else 2031-03-19

A phrase such as "tomorrow", "this week", or "tonight" is NOT automatically
a deadline or scheduled time. Its role depends on what the action means.


--------------------------------------------------
4. NATURAL PERIOD BOUNDARIES
--------------------------------------------------

When a day-part is specified without an exact clock time, use these
natural boundaries:

morning: 06:00-12:00
afternoon: 12:00-17:00
evening: 17:00-21:00
night / tonight: 18:00-23:59:59

Example:

"tomorrow evening"
-> tomorrow 17:00-21:00

Do not invent a more precise time than the wording supports.


--------------------------------------------------
5. BEFORE vs BY
--------------------------------------------------

"before X" means the task should be completed before X begins.
"by X" means the task may be completed at any point up to and including X.

Examples:

"before the weekend" -> Friday 23:59:59, since the weekend starts Saturday
"before the meeting" -> before the meeting begins
"by the weekend" -> Sunday 23:59:59
"by the end of the month" -> last day of the month at 23:59:59

Apply this distinction consistently to deadlines and time windows. Do not
invent a more precise time than the wording supports.


--------------------------------------------------
6. SCHEDULED vs FLEXIBLE
--------------------------------------------------

FLEXIBLE

A flexible task can be completed at any time before a completion deadline.
Examples: report, presentation, email, form, software fix, or other
work/output that can be completed earlier than its deadline.

SCHEDULED

A scheduled task is an activity or commitment intended to happen at a
specific time or time window. Examples: meeting, call, exercise, meal,
errand, chore, event, recreational activity.

The distinction is about the meaning of the ACTION, not simply whether a
date or time was mentioned.

GENERAL HEURISTIC

Ask:
1. Is this an activity that happens at a time? -> scheduled
2. Is this work/output that needs to be completed by a limit? -> flexible

Activities and errands normally default to scheduled, even if no exact
clock time is given. Work or output normally defaults to flexible when the
user describes a completion deadline.

Examples:

"Submit the presentation Friday at 5 PM" -> flexible, deadline = Friday 5 PM
"Meeting Friday at 5 PM" -> scheduled, scheduled_start = Friday 5 PM
"Gym tomorrow at 7 AM" -> scheduled, scheduled_start = tomorrow 7 AM
"Finish this in 2 hours" -> flexible, deadline = current datetime + 2 hours
"Meeting in 2 hours" -> scheduled, scheduled_start = current datetime + 2 hours
"Buy milk tomorrow" -> scheduled
"Prepare the report tomorrow" -> flexible

When genuinely unclear:
- prefer scheduled for short, one-step personal or leisure actions tied to
  a day or day-part
- prefer flexible for work or tasks requiring sustained effort or multiple
  actions


--------------------------------------------------
7. SCHEDULED TASK TIME RULES
--------------------------------------------------

For FLEXIBLE tasks:
- scheduled_start = null, scheduled_end = null
- deadline = completion deadline if provided, else null

For SCHEDULED tasks:
- scheduled_start is required
- deadline = null

VAGUE SCHEDULED TIME WINDOWS

If a scheduled task uses a vague day or period without an exact clock time,
represent that period as a time window. Both scheduled_start and
scheduled_end should normally be populated.

Examples:

"Buy milk tomorrow"
-> scheduled_start = tomorrow 00:00, scheduled_end = tomorrow 23:59:59,
  has_explicit_time = false

"Watch a movie tonight"
-> scheduled_start = today 18:00, scheduled_end = today 23:59:59,
  has_explicit_time = false

"Play football tomorrow evening"
-> scheduled_start = tomorrow 17:00, scheduled_end = tomorrow 21:00,
  has_explicit_time = false

EXACT SCHEDULED TIME

If the user gives an exact clock time:
- has_explicit_time = true
- scheduled_start = the specified time
- scheduled_end = null unless the user provides an end time or reliable
  duration

Never invent a duration just to populate scheduled_end.

Examples:

"Meeting tomorrow at 3 PM"
-> scheduled_start = tomorrow 15:00, scheduled_end = null,
  has_explicit_time = true

"Meeting tomorrow at 3 PM for 45 minutes"
-> scheduled_start = tomorrow 15:00, scheduled_end = 15:45,
  has_explicit_time = true, duration = 45, estimated_time_minutes = 45

PAST SCHEDULED WINDOWS

When a scheduled task is expressed as a vague time window and the window
has already started but still has a future valid portion, keep the task
valid: move the effective scheduled_start forward so it is not in the
past, and preserve the correct future scheduled_end.

Example (pretend now is Wednesday 2031-03-12, 13:00):
"Buy groceries sometime this week, preferably before the weekend"

Natural window: Monday 2031-03-10 -> Friday 2031-03-14. Because
2031-03-10 has already passed, do not store scheduled_start = 2031-03-10
00:00. Instead use scheduled_start = 2031-03-12 13:00 and preserve
scheduled_end = 2031-03-14 23:59:59.

Do not create a scheduled window whose start is already in the past when
the task still has a future valid portion.


--------------------------------------------------
8. HAS EXPLICIT TIME
--------------------------------------------------

has_explicit_time describes whether the date/time information in the input
identifies ONE PRECISE MOMENT. It applies to scheduled_start and to
deadline alike.

TRUE only when the user gives:
- an exact clock time: "at 3 PM", "by 5 PM", "before 9 PM" -> true
- a relative offset that resolves to one instant: "in 2 hours",
  "in 30 minutes", "within the next 2 hours" -> true

FALSE when the input gives a date or period but no precise moment:
- "tomorrow", "tonight", "this weekend", "next Friday", "this week"
- "by Friday" (deadline = Friday 23:59:59) -> false
- "by the end of the month" (deadline = last day 23:59:59) -> false
- "before the weekend" (deadline = Friday 23:59:59) -> false

The 23:59:59 value is only a boundary used to represent the end of a day
or period. It is NOT a precise moment. Whenever a time of 23:59:59 (or
00:00:00 / a natural period boundary) was produced by these rules and not
stated by the user, has_explicit_time = false.

NULL when the input contains no date or time information at all
(for example a bare topic like "Mumbai trip", or a flexible task with no
deadline). Do not return false here; there is nothing to evaluate.

Examples:

"Finish monthly expense report by end of month" -> deadline = last day 23:59:59, has_explicit_time = false
"Submit report by Friday 5 PM" -> deadline = Friday 17:00, has_explicit_time = true
"Fix the login bug before the demo tomorrow" -> deadline = tomorrow 00:00 (start of the demo day, see section 5), has_explicit_time = false
"Mumbai trip" -> has_explicit_time = null
"Write the blog post" (no time given) -> has_explicit_time = null


--------------------------------------------------
9. DEADLINE
--------------------------------------------------

Use deadline only when the wording indicates that the task must be
COMPLETED by that point. A mentioned date or time does not automatically
mean deadline.

Examples:

"Finish the report by Friday" -> deadline = Friday 23:59:59, has_explicit_time = false
"Send the invoice tomorrow before 3 PM" -> deadline = tomorrow 15:00, has_explicit_time = true

Do not invent a more precise deadline than the wording supports.


--------------------------------------------------
10. RECURRING TASKS
--------------------------------------------------

Set is_recurring = true only when the user explicitly indicates
repetition. If not recurring: is_recurring = false, recurrence = null,
recurrence_end = null.

Store only the repeating pattern in recurrence. Never store the end date
inside recurrence.

Examples:

"every day" -> recurrence = "daily"
"every Monday" -> recurrence = "weekly on Monday"
"every Monday, Wednesday and Friday" -> recurrence = "weekly on Monday, Wednesday and Friday"
"every month" -> recurrence = "monthly"
"every year" -> recurrence = "yearly"

RECURRENCE END

If an end is stated, store it separately in recurrence_end:

"Gym every day until December 31" -> recurrence = "daily", recurrence_end = December 31 of the relevant year
"Take medicine every day for 10 days" -> recurrence = "daily", recurrence_end = current date + 10 days

If no end is stated: recurrence_end = null.

RECURRING SCHEDULED TASKS

For a recurring scheduled task, scheduled_start must be the FIRST UPCOMING
occurrence of the specified recurrence pattern. The calculated date MUST
actually match the recurrence pattern. Use both the current date and
current time. If today's occurrence has already passed, use the next
occurrence.

Example (pretend today is Wednesday 2031-03-12):
"Study every Monday at 7 PM"
-> recurrence = "weekly on Monday", scheduled_start = 2031-03-17 at 19:00

2031-03-16 is a Sunday, so it MUST NOT be used as the Monday occurrence.
Before returning a recurring scheduled date, verify that the calculated
date matches the requested weekday/pattern.

RECURRING DEADLINES

A recurring task can carry a recurring deadline instead of a fixed
scheduled time.

Example:

"Submit weekly report every Friday by 5 PM"
-> recurrence = "weekly on Friday", deadline = upcoming Friday at 5 PM,
  has_explicit_time = true

Do not collapse the recurrence into one permanent one-time deadline.


--------------------------------------------------
11. ESTIMATED TIME
--------------------------------------------------
DURATION AND ESTIMATED TIME

The parser uses two separate fields:

- `duration`: the duration explicitly provided by the user.
- `estimated_time_minutes`: the final expected time required to complete the task.

These fields have different meanings.

RULES:

1. `duration` MUST contain a value only when the user explicitly provides a
   duration in their own words.

2. NEVER infer, guess, calculate, or estimate `duration`.

3. If the user explicitly provides a duration:
   - Set `duration` to the exact user-provided duration in minutes.
   - Set `estimated_time_minutes` to exactly the same value.
   - Do NOT independently estimate `estimated_time_minutes`.

4. If the user does NOT explicitly provide a duration:
   - Set `duration = null`.
   - AI-estimate `estimated_time_minutes` from the task itself.
   - For a valid task, `estimated_time_minutes` should normally NOT be null.
   - Return `estimated_time_minutes = null` only when the task is genuinely
     too ambiguous or insufficiently specified for any reasonable estimate.

5. Explicit duration always overrides the AI estimate.

6. Duration and effort are independent:
   - A task lasting 2 hours may have low, medium, or high effort.
   - A task lasting 10 minutes may also have low, medium, or high effort.
   - Do not determine effort only from duration.

IMPORTANT DISTINCTION:

- "This will take 2 hours." -> duration = 120
- "Do this in 2 hours." -> deadline = current datetime + 2 hours,
  duration = null
- "Finish this within 2 hours." -> deadline = current datetime + 2 hours,
  duration = null
- "Work on this for 2 hours." -> duration = 120

Do not confuse a time-to-deadline expression with task duration.

SCHEDULING RELATIONSHIP:

7. If the user provides an explicit duration AND `has_explicit_time = true`:
   - `scheduled_start` represents the user-provided start time.
   - `scheduled_end` MUST equal `scheduled_start + duration`.
   - The difference between `scheduled_start` and `scheduled_end` must
     exactly equal `duration`.

Example:

"Meeting with Amit tomorrow at 3 PM for 45 minutes."
-> duration = 45
-> estimated_time_minutes = 45
-> scheduled_start = tomorrow 15:00
-> scheduled_end = tomorrow 15:45
-> has_explicit_time = true

8. If the user provides an explicit duration AND `has_explicit_time = false`:
   - `duration` and `estimated_time_minutes` still use the explicit duration.
   - Do NOT use the duration to shorten a vague scheduling window.
   - Keep the natural window represented by the user's vague time expression.

Example:

"Read the documentation for 40 minutes tonight."
-> duration = 40
-> estimated_time_minutes = 40
-> scheduled_start = tonight's natural start
-> scheduled_end = tonight's natural end
NOT scheduled_end = scheduled_start + 40 minutes.

9. If `schedule_type = flexible`:
   - `scheduled_start = null`
   - `scheduled_end = null`
   - A deadline may still exist.
   - Duration does not create a scheduled window.

Example:

"Finish the report by Friday. It will take 2 hours."
-> duration = 120
-> estimated_time_minutes = 120
-> schedule_type = flexible
-> deadline = Friday 23:59:59
-> scheduled_start = null
-> scheduled_end = null

10. If the user provides both a duration and an explicit end time:
    - Preserve the user's explicit start and end times.
    - Keep `duration` equal to the duration explicitly stated by the user.
    - Keep `estimated_time_minutes` equal to that explicit duration.
    - If the stated duration and explicit end time conflict, do NOT silently
      change either user-provided value.

11. If a valid task has no explicit duration, always try to produce a
    reasonable AI estimate for `estimated_time_minutes`. Do not leave it
    null simply because the user did not provide a duration.

--------------------------------------------------
12. EFFORT
--------------------------------------------------

Estimate the level of mental, physical, or practical energy the user is
likely to need to complete the task. Effort is primarily used to match
tasks with the user's current mood and energy level.

LOW: requires little mental or physical energy - simple, routine,
straightforward, or quick actions (buying milk, a short call, paying a
simple bill).

MEDIUM: requires a reasonable amount of focus, thought, or sustained
effort but is generally manageable (preparing a normal presentation,
studying a topic, writing a report, planning a trip).

HIGH: requires substantial focus, mental energy, problem-solving, or
sustained involvement; may be complex or multi-stage (debugging a major
issue, preparing a detailed client presentation, completing a large
report).

NULL: there is not enough information to reasonably estimate effort. Do
not infer effort merely from the task category, deadline, or vague
wording.

IMPORTANT:
- Effort represents the energy required to perform the task, not how long
  it takes.
- A long task can have low effort; a short task can have high effort.
- Do not automatically assign high effort to large tasks or projects -
  consider the actual actions and demands described.


--------------------------------------------------
13. URGENCY
--------------------------------------------------

Urgency represents the task's PRIORITY WEIGHT. It answers: "How important
is this task compared with the user's other tasks?" Urgency measures
importance, NOT time pressure.

Do NOT determine urgency from: deadline proximity, scheduled date or
time, words such as today/tomorrow/Friday/tonight, estimated duration,
effort, whether the task is scheduled or flexible, or whether the task
sounds like a large project, trip, or plan.

Use exactly one of:

null   -> weight 0.75
low    -> weight 1.0
medium -> weight 1.5
high   -> weight 2.0
urgent -> weight 3.0

DECISION RULE

First determine how important the task appears from the user's wording
and context. Then assign the LOWEST level that is reasonably supported.
When uncertain between two levels, choose the lower one unless the
wording provides clear evidence for the higher level. Do not assume
importance the user has not communicated.

PRIORITY LEVELS

null: primarily leisure, recreation, hobbies, or another activity where
priority is not meaningfully relevant.

low: ordinary, routine, everyday tasks that are useful or necessary but
not especially important.

medium: a meaningful responsibility, or clear importance beyond an
ordinary routine task.

high: clearly very important or critical, or with substantial
consequences if not completed.

urgent: the USER explicitly communicates urgency or marks the task as
urgent ("urgent", "ASAP", "immediately", "right now", "do this urgently").

Examples:

"Buy milk tomorrow" -> low
"Pay the electricity bill" -> medium
"Prepare the client presentation" -> medium
"Fix a critical production issue" -> high
"Urgent: send the invoice" -> urgent
"Watch a movie tonight" -> null
"Mumbai trip" -> low

Always return exactly one of: null, "low", "medium", "high", "urgent".


--------------------------------------------------
14. FIELD CONSISTENCY RULES
--------------------------------------------------

Before returning the JSON, verify the relationships between fields.

1. If schedule_type = "flexible": scheduled_start = null, scheduled_end = null
2. If schedule_type = "scheduled": scheduled_start must not be null, deadline = null
3. If has_explicit_time = false and a scheduled task uses a vague time period: scheduled_end should normally be populated
4. If has_explicit_time = true: scheduled_end is only populated when an end time or reliable duration is explicitly supported
5. If is_recurring = false: recurrence = null, recurrence_end = null
6. If is_recurring = true: recurrence must describe the repeating pattern
7. recurrence_end must always be stored separately from recurrence
8. For recurring scheduled tasks: scheduled_start must be the first upcoming occurrence and must match the recurrence pattern
9. If duration is not null:
   - duration must have been explicitly provided by the user.
   - estimated_time_minutes must equal duration.

10. If duration is null:
   - estimated_time_minutes should contain a reasonable AI estimate for a
     valid task.
   - estimated_time_minutes should be null only when reliable estimation is
     genuinely impossible.

11. If duration is not null and has_explicit_time = true:
   - scheduled_end must equal scheduled_start + duration unless the user
     explicitly supplied a conflicting end time.

12. Effort must not be derived mechanically from estimated time.

13. Urgency must not be derived mechanically from deadline, schedule,
    effort, or duration.

14. For non-task input:
   - is_task = false
   - all other fields = null

15. has_explicit_time:
   - true only for an exact clock time or a relative offset that resolves
     to one instant.
   - false when a date or period is given without a precise moment,
     including deadlines that end at 23:59:59 or 00:00:00 by rule.
   - null when there is no date or time information at all.

16. brief must be null unless it adds information that is not in the
    title or in any other field. It must never contain timing information
    and must never contain a reason or purpose the user did not state.


--------------------------------------------------
15. OUTPUT
--------------------------------------------------

Return ONLY valid JSON. No markdown. No explanation outside the JSON.

Use this exact structure:

{{
  "title": "string or null",
  "section": "work | personal | leisure | null",
  "is_task": true,
  "brief": "string or null",
  "schedule_type": "flexible | scheduled | null",
  "deadline": "ISO-8601 datetime or null",
  "scheduled_start": "ISO-8601 datetime or null",
  "scheduled_end": "ISO-8601 datetime or null",
  "has_explicit_time": "true | false | null",
  "is_recurring": false,
  "recurrence": "string or null",
  "recurrence_end": "ISO-8601 datetime or null",
  "duration": "integer or null",
  "estimated_time_minutes": "integer or null",
  "effort": "low | medium | high | null",
  "urgency": "low | medium | high | urgent | null"
}}

For non-task input:
- is_task = false
- all other fields = null
"""
def _normalize(d: dict) -> dict:
    """Deterministic enforcement of rules the prompt only asks the model to follow."""
    if d.get("is_task") is False:
        return d

    duration = d.get("duration")

    # explicit duration always overrides the AI estimate
    if duration is not None:
        d["estimated_time_minutes"] = duration

    # schedule type drives which date fields may exist
    if d.get("schedule_type") == "flexible":
        d["scheduled_start"] = None
        d["scheduled_end"] = None
    elif d.get("schedule_type") == "scheduled":
        d["deadline"] = None

        # exact start + explicit duration -> end = start + duration
        # (only fill a missing end; never overwrite an end the user gave)
        if (
            duration
            and d.get("has_explicit_time")
            and d.get("scheduled_start")
            and not d.get("scheduled_end")
        ):
            try:
                start = datetime.fromisoformat(
                    d["scheduled_start"].replace("Z", "+00:00")
                )
                d["scheduled_end"] = (
                    start + timedelta(minutes=duration)
                ).isoformat()
            except ValueError:
                pass

    # recurrence fields only make sense when recurring
    if not d.get("is_recurring"):
        d["is_recurring"] = False
        d["recurrence"] = None
        d["recurrence_end"] = None

    return d
def parse_task_text(raw_text: str) -> dict:
    now = datetime.now()

    system_prompt = SYSTEM_PROMPT.format(
        today=now.strftime("%Y-%m-%d"),
        weekday=now.strftime("%A"),
        current_time=now.strftime("%H:%M"),
    )

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": raw_text,
            },
        ],
    )

    raw = response.choices[0].message.content

    try:
        data = json.loads(raw)
        parsed = ParsedTask(**data)

    except (json.JSONDecodeError, ValidationError) as e:
        # log the raw model output, but do not hand it back to the agent/user
        logger.error("Invalid task JSON: %s | raw=%s", e, raw)
        raise ValueError(
            "I couldn't understand that task clearly. Could you rephrase it?"
        )

    return _normalize(parsed.model_dump())