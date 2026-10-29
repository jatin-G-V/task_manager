
"""LLM client for Sorted's chat agent.

The chat agent uses Gemini through its OpenAI-compatible endpoint,
with Groq as an optional fallback.
"""

import logging
import os
import time
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.services.groq_client import groq_client

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)

PROVIDER = os.environ.get("AGENT_PROVIDER", "gemini").strip().lower()
PRIMARY_MODEL = os.environ.get("AGENT_MODEL", "").strip()
BASE_URL = os.environ.get(
    "AGENT_BASE_URL", DEFAULT_BASE_URL
).strip()
FALLBACK_TO_GROQ = (
    os.environ.get("AGENT_FALLBACK_TO_GROQ", "1").strip() == "1"
)
TIMEOUT_SECONDS = float(
    os.environ.get("AGENT_TIMEOUT_SECONDS", "40")
)
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "2048"))
REASONING_EFFORT = os.environ.get(
    "AGENT_REASONING_EFFORT", "off"
).strip().lower()
TEMPERATURE = 0.2

_primary: Optional[OpenAI] = None

if PROVIDER not in ("gemini", "groq"):
    raise ValueError(
        f"Unsupported AGENT_PROVIDER={PROVIDER!r}; "
        "use gemini or groq"
    )

if PROVIDER != "groq":
    _api_key = os.environ.get("AGENT_API_KEY", "").strip()

    if not _api_key or not PRIMARY_MODEL:
        logger.warning(
            "Primary provider configuration missing; "
            "the agent will use Groq."
        )
    else:
        _primary = OpenAI(
            api_key=_api_key,
            base_url=BASE_URL,
            timeout=TIMEOUT_SECONDS,
            max_retries=0,
        )
        logger.info(
            "Agent primary provider=%s model=%s "
            "timeout=%ss reasoning_effort=%s",
            PROVIDER,
            PRIMARY_MODEL,
            TIMEOUT_SECONDS,
            REASONING_EFFORT,
        )


def _simplify_schema(node):
    """Remove null alternatives from tool schemas."""
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "type" and isinstance(value, list):
                non_null = [item for item in value if item != "null"]
                out[key] = (
                    non_null[0] if len(non_null) == 1 else non_null
                )
            elif key == "enum" and isinstance(value, list):
                out[key] = [
                    item for item in value if item is not None
                ]
            else:
                out[key] = _simplify_schema(value)
        return out

    if isinstance(node, list):
        return [_simplify_schema(item) for item in node]

    return node


_simplified_cache = {}


def _simplified_tools(tools: list) -> list:
    key = id(tools)
    if key not in _simplified_cache:
        _simplified_cache[key] = _simplify_schema(tools)
    return _simplified_cache[key]


def message_to_dict(msg) -> dict:
    """Serialize an assistant response while preserving tool metadata."""
    if isinstance(msg, dict):
        out = dict(msg)
    elif hasattr(msg, "model_dump"):
        out = msg.model_dump(exclude_none=True)
    else:
        out = dict(vars(msg))

    out["role"] = "assistant"
    out.setdefault("content", "")

    message_extra = getattr(msg, "extra_content", None)
    if message_extra and "extra_content" not in out:
        out["extra_content"] = message_extra

    original_calls = getattr(msg, "tool_calls", None) or []
    serialized_calls = out.get("tool_calls") or []

    for original, serialized in zip(
        original_calls, serialized_calls
    ):
        if not isinstance(serialized, dict):
            continue
        for field in ("extra_content", "thought_signature"):
            value = getattr(original, field, None)
            if value and field not in serialized:
                serialized[field] = value

    return out


def _messages_for_groq(messages: list) -> list:
    """Remove Gemini-specific metadata before Groq fallback."""
    clean = []

    for msg in messages:
        if not isinstance(msg, dict):
            clean.append(msg)
            continue

        item = {
            key: value
            for key, value in msg.items()
            if key not in ("extra_content", "thought_signature")
        }

        if item.get("tool_calls"):
            item["tool_calls"] = [
                {
                    key: value
                    for key, value in call.items()
                    if key not in (
                        "extra_content",
                        "thought_signature",
                    )
                }
                if isinstance(call, dict)
                else call
                for call in item["tool_calls"]
            ]

        clean.append(item)

    return clean


def call_groq(messages: list, tools=None):
    kwargs = {
        "model": GROQ_MODEL,
        "messages": _messages_for_groq(messages),
        "temperature": TEMPERATURE,
        "reasoning_effort": "medium",
    }

    if tools:
        kwargs["tools"] = tools
        kwargs["parallel_tool_calls"] = False

    return groq_client.chat.completions.create(**kwargs)


def call_primary(messages: list, tools=None):
    if _primary is None:
        raise RuntimeError(
            "Primary agent provider is not configured."
        )

    kwargs = {
        "model": PRIMARY_MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    # "off" omits this parameter; it does not guarantee
    # that the model performs no internal reasoning.
    if REASONING_EFFORT and REASONING_EFFORT != "off":
        kwargs["reasoning_effort"] = REASONING_EFFORT

    if tools:
        kwargs["tools"] = _simplified_tools(tools)
        kwargs["tool_choice"] = "auto"

    logger.info(
        "Primary request config: provider=%s timeout=%ss "
        "model=%s reasoning_effort_sent=%s tool_count=%s",
        PROVIDER,
        TIMEOUT_SECONDS,
        PRIMARY_MODEL,
        "reasoning_effort" in kwargs,
        len(tools or []),
    )

    started = time.monotonic()

    try:
        response = _primary.chat.completions.create(**kwargs)
    except Exception:
        logger.exception(
            "Primary API request failed after %.2fs",
            time.monotonic() - started,
        )
        raise

    logger.info(
        "Primary API request completed in %.2fs",
        time.monotonic() - started,
    )
    return response


def chat(messages: list, tools=None):
    """Return (response, provider_name), using Groq on failure if enabled."""
    if _primary is not None:
        started = time.monotonic()

        try:
            response = call_primary(messages, tools)
            return response, PROVIDER

        except Exception as exc:
            duration = time.monotonic() - started

            logger.warning(
                "%s agent call failed after %.2fs (%s: %s)%s",
                PROVIDER,
                duration,
                type(exc).__name__,
                str(exc)[:1000],
                (
                    " - falling back to Groq"
                    if FALLBACK_TO_GROQ
                    else ""
                ),
            )

            if not FALLBACK_TO_GROQ:
                raise

    started = time.monotonic()

    try:
        response = call_groq(messages, tools)
    except Exception:
        logger.exception(
            "Groq agent call failed after %.2fs",
            time.monotonic() - started,
        )
        raise

    logger.info(
        "Groq agent call completed in %.2fs",
        time.monotonic() - started,
    )
    return response, "groq"
