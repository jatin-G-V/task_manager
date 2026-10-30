import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import get_current_user
from app.services import reply_writer

logger = logging.getLogger(__name__)

router = APIRouter()

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 15
_hits: dict = {}


def _rate_limit(key: str) -> None:
    now = time.time()
    recent = [t for t in _hits.get(key, []) if now - t < _RATE_WINDOW_SECONDS]
    if len(recent) >= _RATE_MAX_REQUESTS:
        _hits[key] = recent
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    recent.append(now)
    _hits[key] = recent


class StyleRequest(BaseModel):
    style_note: str = ""


@router.get("/settings/style")
def get_style(request: Request, user_id: str = Depends(get_current_user)):
    _rate_limit(f"user:{user_id}")
    note = reply_writer.get_style_note(user_id)
    return {"style_note": note or "", "max_chars": reply_writer.MAX_NOTE_CHARS}


@router.put("/settings/style")
def put_style(
    req: StyleRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    _rate_limit(f"user:{user_id}")
    _rate_limit(f"ip:{request.client.host if request.client else 'unknown'}")

    if len(req.style_note) > reply_writer.MAX_NOTE_CHARS * 2:
        raise HTTPException(status_code=400, detail="That note is too long.")

    try:
        note = reply_writer.set_style_note(user_id, req.style_note)
    except Exception:
        logger.exception("Could not save style note")
        raise HTTPException(status_code=503, detail="Could not save right now. Please try again.")

    return {"style_note": note or "", "max_chars": reply_writer.MAX_NOTE_CHARS}