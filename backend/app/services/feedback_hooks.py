"""Logs the user's answer to a duplicate / part-of question.

Installed once at startup (see routers/feedback.py). It wraps resolve_pending
without changing its behaviour: the original runs first and its result or
error is returned exactly as before.
"""

import logging

from app.services import agent_tools
from app.services.feedback_log import log_event

logger = logging.getLogger(__name__)

_CHOICES = {"keep_existing", "update_existing", "add_separate", "merge"}


def _snapshot(user_id: str, args: dict):
    """Read the question being answered BEFORE resolve_pending changes it."""
    try:
        state = agent_tools._pending.get(user_id)
        if not state or not state.get("queue"):
            return None

        conflict = state["queue"][0]
        if conflict.get("kind", "duplicate") != "duplicate":
            return None  # clashes and past-time questions are not duplicate decisions

        relation = conflict.get("relation")
        choice = args.get("choice")
        # same rule resolve_pending applies: merging a plain duplicate means keep
        if relation == "duplicate" and choice == "merge":
            choice = "keep_existing"
        if choice not in _CHOICES:
            return None

        target = conflict.get("target") or {}
        return {
            "task_id": target.get("id"),
            "payload": {
                "relation": relation,          # duplicate | part_of
                "choice": choice,
                "same_time": conflict.get("new_when") == target.get("when"),
            },
        }
    except Exception:
        logger.warning("Could not read duplicate decision", exc_info=True)
        return None


def install() -> None:
    funcs = agent_tools.TOOL_FUNCTIONS
    original = funcs.get("resolve_pending")
    if original is None or getattr(original, "_feedback_wrapped", False):
        return

    def resolve_pending_logged(user_id: str, args: dict):
        snap = _snapshot(user_id, args)
        result = original(user_id, args)  # errors pass through untouched
        if snap:
            log_event(user_id, "dup_decision", task_id=snap["task_id"], payload=snap["payload"])
        return result

    resolve_pending_logged._feedback_wrapped = True
    # same dict object agent.py imported, so the agent picks this up
    funcs["resolve_pending"] = resolve_pending_logged
    logger.info("Feedback hook installed for resolve_pending")