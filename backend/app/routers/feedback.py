import logging
import re
import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.db.supabase_client import supabase
from app.services import feedback_hooks
from app.services.feedback_log import log_event
from app.services.timeutil import now_local

logger = logging.getLogger(__name__)

router = APIRouter()

# attaches the duplicate-decision logging to the agent's resolve_pending
feedback_hooks.install()

MONTHLY_LIMIT = 2
MIN_LEN = 10
MAX_LEN = 500
MAX_CONTEXT_MESSAGES = 6
MAX_CONTEXT_CHARS = 300

# tiny in-memory limiter (single worker, same assumption as the pending decisions)
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 10
_hits: dict = {}

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _month_key() -> str:
    # app timezone, so the month changes at local midnight, not at UTC midnight
    return f"{now_local():%Y-%m}"


def _clean(text: str) -> str:
    text = _CONTROL_CHARS.sub("", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _rate_limit(key: str) -> None:
    now = time.time()
    recent = [t for t in _hits.get(key, []) if now - t < _RATE_WINDOW_SECONDS]
    if len(recent) >= _RATE_MAX_REQUESTS:
        _hits[key] = recent
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    recent.append(now)
    _hits[key] = recent


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _used_this_month(user_id: str) -> int:
    result = (
        supabase
        .table("user_feedback")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("month_key", _month_key())
        .execute()
    )
    return result.count or 0


# ============================================================
# Quota
# ============================================================

@router.get("/feedback/quota")
def feedback_quota(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    _rate_limit(f"user:{user_id}")
    _rate_limit(f"ip:{_client_ip(request)}")

    try:
        used = _used_this_month(user_id)
    except Exception:
        logger.exception("Could not read feedback quota")
        raise HTTPException(status_code=503, detail="Feedback is temporarily unavailable.")

    return {
        "used": used,
        "limit": MONTHLY_LIMIT,
        "remaining": max(0, MONTHLY_LIMIT - used),
        "month": _month_key(),
    }


# ============================================================
# Written feedback (max 2 per calendar month)
# ============================================================

class ContextMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class FeedbackRequest(BaseModel):
    type: Literal["bug", "suggestion", "other"]
    message: str
    include_context: bool = False
    context_messages: list[ContextMessage] = Field(default_factory=list)
    app_version: Optional[str] = None


@router.post("/feedback")
def submit_feedback(
    req: FeedbackRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    _rate_limit(f"user:{user_id}")
    _rate_limit(f"ip:{_client_ip(request)}")

    message = _clean(req.message)
    if len(message) < MIN_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Please write at least {MIN_LEN} characters.",
        )
    if len(message) > MAX_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Please keep it under {MAX_LEN} characters.",
        )

    # Chat text is attached only when the user ticked the box.
    context = None
    if req.include_context and req.context_messages:
        context = {
            "messages": [
                {
                    "role": item.role,
                    "content": _clean(item.content)[:MAX_CONTEXT_CHARS],
                }
                for item in req.context_messages[-MAX_CONTEXT_MESSAGES:]
            ]
        }

    app_version = _clean(req.app_version or "")[:40] or None

    try:
        result = supabase.rpc(
            "submit_feedback",
            {
                "p_user_id": user_id,
                "p_type": req.type,
                "p_message": message,
                "p_context": context,
                "p_app_version": app_version,
                "p_month_key": _month_key(),
                "p_limit": MONTHLY_LIMIT,
            },
        ).execute()
    except Exception:
        logger.exception("Feedback submit failed")
        raise HTTPException(status_code=503, detail="Feedback is temporarily unavailable.")

    data = result.data or {}
    if not data.get("ok"):
        raise HTTPException(
            status_code=429,
            detail="You've used both feedback slots this month. Thank you for the earlier notes!",
        )

    return {
        "status": "received",
        "used": data.get("used"),
        "limit": data.get("limit", MONTHLY_LIMIT),
        "remaining": max(0, MONTHLY_LIMIT - int(data.get("used") or 0)),
    }


# ============================================================
# Thumbs up / down on an assistant reply
# ============================================================

class ThumbEvent(BaseModel):
    value: Literal["up", "down"]
    # Stored so the rating is understandable later. Sent only when the user taps.
    reply_text: Optional[str] = None
    user_message: Optional[str] = None
    # optional quick reason, only meaningful for a thumbs down
    reason: Optional[Literal["wrong_task", "wrong_time", "not_helpful", "other"]] = None
    # app-generated id of the bubble; if the user changes their mind, the latest wins
    message_id: Optional[str] = None
    task_id: Optional[str] = None


@router.post("/feedback/event")
def thumb_event(
    req: ThumbEvent,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    _rate_limit(f"user:{user_id}")
    _rate_limit(f"ip:{_client_ip(request)}")

    log_event(
        user_id,
        "thumb",
        task_id=req.task_id,
        payload={
            "value": req.value,
            "reason": req.reason,
            "message_id": _clean(req.message_id or "")[:64] or None,
            "reply_text": _clean(req.reply_text or "")[:400] or None,
            "user_message": _clean(req.user_message or "")[:200] or None,
        },
    )
    return {"status": "ok"}