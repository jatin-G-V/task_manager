"""Recommendation tools that also write their own reply.

The ranking engine returns a `reason` for every pick. The reply text is built
here from that reason, so no second LLM call is needed.

The server remembers which tasks it already suggested to a user, because the
chat history the app sends is plain text and carries no task ids. A call that
asks for "something else" (another=true, or any exclude_ids) skips them.
"""

import copy
import re
import time

from app.services import agent_tools, task_service
from app.services.agent_tools import _quoted, _task_view
from app.services.taskfmt import clock, day_word
from app.services.timeutil import to_local

EMPTY_REPLY = "Nothing needs attention right now."
NO_MORE_REPLY = "That's everything I'd suggest right now. Ask again later or add a new task."

SHOWN_TTL_SECONDS = 1800

# user_id -> {"expires": <timestamp>, "ids": [task id, ...]}
# In memory, same single-worker assumption as the pending decisions.
_shown = {}

_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")

_ANOTHER_NOTE = (
    " If the user asks for something else, another, anything else or the next "
    "suggestion, call this SAME tool again with another=true. The system "
    "remembers what was already shown: never use list_tasks for this and "
    "never invent ids."
)
_ANOTHER_PROPERTY = {
    "type": "boolean",
    "description": "true when the user asks for something else / another / next.",
}


def _patch_tool(tool: dict) -> None:
    function = tool.get("function", {})
    if function.get("name") not in ("recommend_task", "recommend_for_mood"):
        return
    properties = function["parameters"].setdefault("properties", {})
    if "another" in properties:
        return
    properties["another"] = copy.deepcopy(_ANOTHER_PROPERTY)
    function["description"] = function.get("description", "") + _ANOTHER_NOTE


def install() -> None:
    """Patch the shared tool schemas in place (called once from main.py)."""
    for tool in agent_tools.TOOLS:
        _patch_tool(tool)


def with_another_flag(tools: list) -> list:
    """Copy of the schemas with the flag added (kept for older agent.py versions)."""
    patched = copy.deepcopy(tools)
    for tool in patched:
        _patch_tool(tool)
    return patched


def _pick(options: list, key) -> str:
    """Stable variant: the same task always gets the same sentence."""
    index = sum(ord(c) for c in str(key or "")) % len(options)
    return options[index]


def _window_phrase(task: dict):
    """A loose time window (no exact time) in plain words, e.g. 'sometime before 5:40 PM'."""
    if task.get("has_explicit_time") or task.get("schedule_type") != "scheduled":
        return None
    end = task.get("scheduled_end") or task.get("scheduled_start")
    if not end:
        return None
    end_local = to_local(end)
    day = day_word(end_local)
    if day == "today":
        return f"sometime before {clock(end_local)}"
    return f"sometime {day} before {clock(end_local)}"


def _reply(view: dict, reason, energy=None) -> str:
    name = _quoted(view.get("title") or "that task")
    when = view.get("when") or ""
    section = view.get("section")
    key = view.get("id") or view.get("title")
    is_due = when.lower().startswith("due")

    if reason == "pinned":
        options = [
            f"Heads up, {name} is on right now" + (f" ({when})." if when else "."),
            f"{name} is happening right now" + (f" ({when})." if when else "."),
        ]
        return _pick(options, key)

    if reason == "deadline_risk":
        if is_due:
            options = [
                f"I'd start with {name}. It's {when}, so it's worth getting on now.",
                f"{name} is your most time-sensitive one: it's {when}. A good place to start.",
            ]
        elif when:
            options = [
                f"I'd start with {name} ({when}). It's the most time-sensitive one.",
                f"{name} is your most time-sensitive task right now ({when}).",
            ]
        else:
            options = [
                f"I'd start with {name}. It's the most time-sensitive one.",
            ]
        return _pick(options, key)

    if reason == "energy_match":
        if energy == "low":
            return _pick(
                [
                    f"Since you're low on energy, {name} is a gentle one to take on.",
                    f"On a low-energy day, {name} is an easy one to get done.",
                ],
                key,
            )
        if energy == "high":
            return _pick(
                [
                    f"You've got the energy, so {name} would make a good focused push.",
                    f"Good time for something meaty: try {name}.",
                ],
                key,
            )
        return f"{name} is a steady pick for how you're feeling."

    # top_score (or anything unknown): nothing is urgent
    if when:
        return _pick(
            [
                f"Nothing is urgent, so you could pick up {name} ({when}).",
                f"Next on your list is {name} ({when}).",
            ],
            key,
        )
    if section == "leisure":
        return _pick(
            [
                f"Nothing is pressing, so you could take a break with {name}.",
                f"You're clear for now, so {name} sounds like a nice way to unwind.",
            ],
            key,
        )
    if section == "work":
        return _pick(
            [
                f"Nothing is pressing, so it's a good moment to get ahead on {name}.",
                f"You're clear for now. {name} would be a good one to move forward.",
            ],
            key,
        )
    return _pick(
        [
            f"Nothing is pressing right now, so {name} is a good one to pick up.",
            f"You're clear for now. How about {name}?",
        ],
        key,
    )


def _excluded_ids(user_id: str, args: dict) -> tuple:
    """Return (ids to skip, whether the user asked for another)."""
    given = [
        str(i) for i in (args.get("exclude_ids") or [])
        if _UUID.match(str(i))
    ]
    another = bool(args.get("another")) or bool(args.get("exclude_ids"))

    state = _shown.get(user_id)
    if state and state["expires"] < time.time():
        state = None
        _shown.pop(user_id, None)

    if another:
        shown = state["ids"] if state else []
        return list(dict.fromkeys(shown + given)), True

    # A fresh question starts the list over.
    _shown.pop(user_id, None)
    return [], False


def _remember(user_id: str, task_id) -> None:
    if not task_id:
        return
    state = _shown.setdefault(user_id, {"expires": 0, "ids": []})
    state["ids"].append(str(task_id))
    state["expires"] = time.time() + SHOWN_TTL_SECONDS


def _build(user_id: str, tasks: list, energy=None, asked_next=False) -> dict:
    if not tasks:
        return {
            "status": "empty",
            "tasks": [],
            "reply": NO_MORE_REPLY if asked_next else EMPTY_REPLY,
        }

    task = tasks[0]
    view = _task_view(task)

    # a loose window reads as "sometime before 5:40 PM", never as a raw time range
    window = _window_phrase(task)
    if window:
        view = {**view, "when": window}

    reason = task.get("reason")
    _remember(user_id, task.get("id"))

    return {
        "status": "ok",
        "tasks": [view],
        "reason": reason,
        "reply": _reply(view, reason, energy),
    }


def recommend_task(user_id: str, args: dict) -> dict:
    exclude_ids, asked_next = _excluded_ids(user_id, args)
    tasks = task_service.recommend_tasks(user_id, limit=1, exclude_ids=exclude_ids)
    return _build(user_id, tasks[:1], asked_next=asked_next)


def recommend_for_mood(user_id: str, args: dict) -> dict:
    energy = args.get("energy")
    if energy not in ("low", "medium", "high"):
        raise ValueError("energy must be low, medium or high.")
    exclude_ids, asked_next = _excluded_ids(user_id, args)
    tasks = task_service.recommend_tasks(
        user_id,
        energy=energy,
        exclude_ids=exclude_ids,
    )
    return _build(user_id, tasks[:1], energy=energy, asked_next=asked_next)