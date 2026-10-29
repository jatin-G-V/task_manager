"""Run the API with concise INFO logs for local manual testing."""

import logging
import json
import os
import sys

import uvicorn

from app.services import agent


def _short_title(value):
    if not isinstance(value, str) or len(value) <= 40:
        return value
    return value[:39] + "…"


def _shorten_titles(value, key=None):
    if key in {"title", "titles"}:
        if isinstance(value, str):
            return _short_title(value)
        if isinstance(value, list):
            return [_short_title(item) for item in value]
    if isinstance(value, dict):
        return {item_key: _shorten_titles(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_shorten_titles(item) for item in value]
    return value


def _install_debug_tool_logging():
    """Enrich agent tool logs only inside this local launcher process."""
    logger = agent.logger
    original_info = logger.info
    show_arguments = os.getenv("LOG_TOOL_ARGS") == "1"

    def debug_info(message, *args, **kwargs):
        if isinstance(message, str) and message.startswith("TOOL call name="):
            if show_arguments:
                frame = sys._getframe(1)
                tool_call = frame.f_locals.get("tc")
                tool_name = getattr(getattr(tool_call, "function", None), "name", "unknown")
                tool_args = _shorten_titles(frame.f_locals.get("args", {}))
                original_info(
                    "TOOL call name=%s args=%s",
                    tool_name,
                    json.dumps(tool_args, ensure_ascii=False, separators=(",", ":"), default=str),
                )
                return

        if isinstance(message, str) and message.startswith("TOOL done name="):
            frame = sys._getframe(1)
            result = frame.f_locals.get("result")
            if show_arguments:
                tool_name = frame.f_locals.get("tc").function.name
                outcome = frame.f_locals.get("outcome", "ok")
                status = result.get("status", outcome) if isinstance(result, dict) else outcome
                reply = result.get("reply", "") if isinstance(result, dict) else ""
                reply = " ".join(reply.split())[:120] if isinstance(reply, str) else ""
                original_info("TOOL done name=%s status=%s reply=%r", tool_name, status, reply)
                return

            if "items=None" in (message % args if args else message):
                tool_name = frame.f_locals.get("tc").function.name
                outcome = frame.f_locals.get("outcome", "ok")
                original_info("TOOL done name=%s outcome=%s", tool_name, outcome)
                return

        original_info(message, *args, **kwargs)

    logger.info = debug_info


if __name__ == "__main__":
    _install_debug_tool_logging()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level="info",
        log_config=None,
    )
