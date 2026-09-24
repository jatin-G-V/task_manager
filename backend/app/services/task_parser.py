import json
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, ValidationError, model_validator

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

    effort: Optional[Literal["low", "medium", "high"]] = None
    urgency: Optional[Literal["low", "medium", "high"]] = None

  
SYSTEM_PROMPT = """
You are an AI task parser for a personal task-management application.

Convert the user's input into structured task information.
Use the meaning of the complete input, not isolated keywords.

Current date: {today} ({weekday})
Current time: {current_time}

--------------------------------------------------
1. TASK vs NON-TASK
--------------------------------------------------

First determine whether the input is an actionable task.

If it is NOT a task:
- is_task = false
- all other fields = null

Do not invent a task from conversational statements.

--------------------------------------------------
2. BASIC INFORMATION
--------------------------------------------------

For a task:

section:
- work: job, university, meetings, clients, professional work
- personal: errands, shopping, travel, household, personal responsibilities
- leisure: entertainment, hobbies, relaxation, recreation

Create a concise title.

Create a brief only when it adds useful information.
Do not invent facts, people, places, requirements, or actions.

--------------------------------------------------
3. SCHEDULING
--------------------------------------------------

Use one of:

flexible:
The task can be completed at a suitable time before its deadline.

scheduled:
The task is intended for a particular day, period, or time.

Examples:

"Finish the report by Friday"
→ flexible + deadline Friday

"Buy milk tomorrow"
→ scheduled

"Meeting tomorrow at 3 PM"
→ scheduled

Do not decide using keywords alone. Use the meaning of the complete task.

For flexible tasks:
- scheduled_start = null
- scheduled_end = null
- deadline = completion deadline, if provided

For scheduled tasks:
- scheduled_start is required
- deadline = null

If the user specifies only a day or general period:
- create the natural start and end boundaries of that period
- has_explicit_time = false

Example:

"Buy milk tomorrow"
→ tomorrow 00:00:00 to 23:59:59

If the user specifies an exact clock time:
- scheduled_start = that time
- has_explicit_time = true
- scheduled_end = null unless the user provides an end time or reliable duration

Example:

"Meeting tomorrow at 3 PM"
→ scheduled_start = 15:00
→ scheduled_end = null
→ has_explicit_time = true

Do NOT invent a duration or scheduled_end from an exact start time.

--------------------------------------------------
4. RECURRING TASKS
--------------------------------------------------

Set is_recurring = true only when the user indicates repetition.

Set recurrence to a concise description of the pattern.

Examples:

"every day at 10" → daily

"every Monday" → weekly on Monday

"every Monday, Wednesday and Friday"
→ weekly on Monday, Wednesday and Friday

"every year" → yearly

"every day until December 31"
→ daily until 2026-12-31

If the task is not recurring:
- is_recurring = false
- recurrence = null

For a recurring scheduled task, scheduled_start MUST be the
FIRST UPCOMING occurrence.

Use BOTH the current date AND current time.

If today's occurrence time has already passed, NEVER use today's
occurrence. Use the next recurrence instead.

Example:

Current date/time:
Wednesday, September 23, 2026, 20:35

"Team standup every day at 10 AM"
→ scheduled_start = 2026-09-24T10:00:00

Do not infer scheduled_end from recurrence.

Only set scheduled_end when:
- the user explicitly provides an end time, or
- the user explicitly provides a duration, or
- the task uses a natural day/period window such as "tomorrow",
  "tomorrow morning", or "tonight".

--------------------------------------------------
5. DEADLINE
--------------------------------------------------

Use deadline when the task must be completed by a particular date or time.

Examples:

"Finish the report by Friday"
→ deadline = Friday


Do not create a deadline merely because a date is mentioned.

Relative date rules:

"this week" means the current calendar week.

For example, if today is Wednesday, September 23, 2026:
"Finish this sometime this week"
→ deadline = Sunday, September 27, 2026 at 23:59:59

you can use Natural time-period boundaries:
- "morning" → 06:00:00 to 12:00:00
- "tonight" → 18:00:00 to 23:59:59
- etc.

Do not invent a more precise date when the user's wording does not
support it.



--------------------------------------------------
6. EFFORT
--------------------------------------------------

Estimate:

- low: simple or quick task
- medium: moderate work
- high: substantial, complex, or time-consuming work

--------------------------------------------------
7. URGENCY
--------------------------------------------------

Estimate urgency from the user's wording, deadline, context,
and consequences.

"ASAP", "urgent", "immediately", or similar language should
increase urgency.

Do not automatically make every task with a deadline highly urgent.

--------------------------------------------------
8. OUTPUT
--------------------------------------------------

Return ONLY valid JSON.

Do not include markdown or explanations.

Always return this complete structure:

{{
  "title": "string or null",
  "section": "work | personal | leisure | null",
  "is_task": true,
  "brief": "string or null",
  "schedule_type": "flexible | scheduled | null",
  "deadline": "ISO-8601 datetime or null",
  "scheduled_start": "ISO-8601 datetime or null",
  "scheduled_end": "ISO-8601 datetime or null",
  "has_explicit_time": true,
  "is_recurring": false,
  "recurrence": "string or null",
  "effort": "low | medium | high | null",
  "urgency": "low | medium | high | null"
}}

For non-task input, all fields except is_task must be null.

"""
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
        raise ValueError(
            f"Model returned invalid task JSON: {e}\nRaw: {raw}"
        )

    return parsed.model_dump()
