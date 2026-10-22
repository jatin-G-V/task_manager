"""
LLM client for the chat agent.

The task parser and the duplicate judge stay on Groq (groq_client.py). Only the
agent loop goes through this module, so the agent can run on another provider.

Configuration (backend/.env):
    AGENT_PROVIDER          nvidia | groq   (default: groq = behaviour before this file)
    AGENT_MODEL             exact model id of the primary provider
    AGENT_API_KEY           key of the primary provider (backend only, never in the app)
    AGENT_BASE_URL          OpenAI-compatible endpoint (default: NVIDIA)
    AGENT_FALLBACK_TO_GROQ  1 = if the primary call fails, retry once on Groq (default 1)
    AGENT_TIMEOUT_SECONDS   primary timeout (default 40)
    AGENT_MAX_TOKENS        reply budget for the primary model (default 2048)
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.services.groq_client import groq_client

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

PROVIDER = os.environ.get("AGENT_PROVIDER", "groq").strip().lower()
PRIMARY_MODEL = os.environ.get("AGENT_MODEL", "").strip()
BASE_URL = os.environ.get("AGENT_BASE_URL", DEFAULT_BASE_URL).strip()
FALLBACK_TO_GROQ = os.environ.get("AGENT_FALLBACK_TO_GROQ", "1").strip() == "1"
TIMEOUT_SECONDS = float(os.environ.get("AGENT_TIMEOUT_SECONDS", "40"))
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "2048"))
TEMPERATURE = 0.1

_primary: Optional[OpenAI] = None

if PROVIDER != "groq":
    _api_key = os.environ.get("AGENT_API_KEY", "").strip()

    if not _api_key or not PRIMARY_MODEL:
        logger.warning(
            "AGENT_PROVIDER=%s but AGENT_API_KEY or AGENT_MODEL is missing; "
            "the agent will use Groq.",
            PROVIDER,
        )
    else:
        # max_retries=0: our own fallback should react at once instead of the SDK
        # silently retrying a rate-limited call with back-off.
        _primary = OpenAI(
            api_key=_api_key,
            base_url=BASE_URL,
            timeout=TIMEOUT_SECONDS,
            max_retries=0,
        )

PRIMARY_ENABLED = _primary is not None


def _simplify_schema(node):
    """Make tool schemas acceptable to stricter providers.

    Turns {"type": ["string", "null"], "enum": ["a", None]} into
    {"type": "string", "enum": ["a"]}. The fields are optional anyway.
    """
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "type" and isinstance(value, list):
                non_null = [t for t in value if t != "null"]
                out[key] = non_null[0] if len(non_null) == 1 else non_null
            elif key == "enum" and isinstance(value, list):
                out[key] = [item for item in value if item is not None]
            else:
                out[key] = _simplify_schema(value)
        return out

    if isinstance(node, list):
        return [_simplify_schema(item) for item in node]

    return node


def message_to_dict(msg) -> dict:
    """Serialize an assistant response without discarding provider metadata.

    Gemini's OpenAI-compatible endpoint can attach a thought signature to a
    tool call. The signature must be replayed unchanged with the assistant
    tool-call message on the next request. Pydantic's dump also retains any
    provider-specific extra fields exposed by the SDK model.
    """
    if isinstance(msg, dict):
        out = dict(msg)
    elif hasattr(msg, "model_dump"):
        out = msg.model_dump(exclude_none=True)
    else:
        out = dict(vars(msg))

    out["role"] = "assistant"
    # OpenAI-compatible chat APIs expect the assistant content key, even when
    # the response only contains tool calls.
    out.setdefault("content", "")

    # Some SDK/provider combinations expose Gemini's signature as an extra
    # attribute rather than including it in model_dump(). Preserve those too.
    message_extra = getattr(msg, "extra_content", None)
    if message_extra and "extra_content" not in out:
        out["extra_content"] = message_extra

    original_calls = getattr(msg, "tool_calls", None) or []
    serialized_calls = out.get("tool_calls") or []
    for original, serialized in zip(original_calls, serialized_calls):
        for field in ("extra_content", "thought_signature"):
            value = getattr(original, field, None)
            if value and field not in serialized:
                serialized[field] = value

    return out


def call_groq(messages: list, tools: Optional[list] = None):
    kwargs = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "reasoning_effort": "medium",
    }

    if tools:
        kwargs["tools"] = tools
        kwargs["parallel_tool_calls"] = False

    return groq_client.chat.completions.create(**kwargs)


def call_primary(messages: list, tools: Optional[list] = None):
    if _primary is None:
        raise RuntimeError("Primary agent provider is not configured.")

    kwargs = {
        "model": PRIMARY_MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    if tools:
        kwargs["tools"] = _simplify_schema(tools)
        kwargs["tool_choice"] = "auto"

    return _primary.chat.completions.create(**kwargs)


def chat(messages: list, tools: Optional[list] = None):
    """Return (response, provider_name). Falls back to Groq if the primary call fails."""
    if _primary is not None:
        try:
            return call_primary(messages, tools), PROVIDER
        except Exception as exc:
            if not FALLBACK_TO_GROQ:
                raise

            logger.warning(
                "%s agent call failed (%s: %s) - falling back to Groq",
                PROVIDER,
                type(exc).__name__,
                str(exc)[:300],
            )

    return call_groq(messages, tools), "groq"
