"""Recommendation tools that also write their own reply.

The ranking engine returns a `reason` for every pick. The reply text is built
here from that reason, so the model does not have to guess how to phrase it
(and no second LLM call is needed).
"""

from app.services import task_service
from app.services.agent_tools import _quoted, _task_view

EMPTY_REPLY = "Nothing needs attention right now."


def _reply(view: dict, reason, energy=None) -> str:
    name = _quoted(view.get("title") or "that task")
    when = view.get("when")
    section = view.get("section")

    if reason == "pinned":
        return f"{name} is happening right now" + (f" ({when})." if when else ".")

    if reason == "deadline_risk":
        if when:
            return f"Start with {name}. Its deadline is close ({when})."
        return f"Start with {name}. Its deadline is close."

    if reason == "energy_match":
        if energy == "low":
            return f"Since your energy is low, {name} is a gentle one to take on."
        if energy == "high":
            return f"{name} is a good fit for a focused push."
        return f"{name} is a steady pick for how you're feeling."

    # top_score (or anything unknown): nothing is urgent
    if when:
        return f"{name} is next up ({when})."
    if section == "leisure":
        return f"Nothing is pressing, so you could take a break with {name}."
    if section == "work":
        return f"Nothing is pressing right now, so {name} is a good one to get ahead on."
    return f"Nothing is pressing right now, so {name} is a good one to pick up."


def _build(tasks: list, energy=None) -> dict:
    if not tasks:
        return {"status": "empty", "tasks": [], "reply": EMPTY_REPLY}

    task = tasks[0]
    view = _task_view(task)
    reason = task.get("reason")
    return {
        "status": "ok",
        "tasks": [view],
        "reason": reason,
        "reply": _reply(view, reason, energy),
    }


def recommend_task(user_id: str, args: dict) -> dict:
    tasks = task_service.recommend_tasks(
        user_id,
        limit=1,
        exclude_ids=args.get("exclude_ids") or [],
    )
    return _build(tasks[:1])


def recommend_for_mood(user_id: str, args: dict) -> dict:
    energy = args.get("energy")
    if energy not in ("low", "medium", "high"):
        raise ValueError("energy must be low, medium or high.")
    tasks = task_service.recommend_tasks(
        user_id,
        energy=energy,
        exclude_ids=args.get("exclude_ids") or [],
    )
    return _build(tasks[:1], energy)