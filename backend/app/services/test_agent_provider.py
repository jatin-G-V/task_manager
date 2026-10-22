"""
Smoke test for the agent LLM provider. Nothing here touches the database.

Run from backend/:
    PYTHONPATH=. python -m app.services.test_agent_provider            # primary provider
    PYTHONPATH=. python -m app.services.test_agent_provider --compare  # primary + Groq baseline
"""

import json
import sys
import time

from app.services.agent import SYSTEM_PROMPT, _context_message
from app.services.agent_client import (
    PRIMARY_ENABLED,
    PRIMARY_MODEL,
    PROVIDER,
    call_groq,
    call_primary,
    message_to_dict,
)
from app.services.agent_tools import TOOLS

BASE = [{"role": "system", "content": SYSTEM_PROMPT}, _context_message()]
PAUSE_SECONDS = 1.5  # stay well under free-tier request limits

CASES = [
    {
        "name": "two tasks in ONE add_tasks call",
        "text": "add gym tomorrow at 7 AM and read a book tomorrow at 9 PM",
        "tool": "add_tasks",
        "check": lambda a: len(a.get("items") or []) >= 2,
    },
    {
        "name": "what should I do now",
        "text": "What should I do right now?",
        "tool": "recommend_task",
        "check": None,
    },
    {
        "name": "tired -> mood tool with low energy",
        "text": "I'm tired, what can I do?",
        "tool": "recommend_for_mood",
        "check": lambda a: a.get("energy") == "low",
    },
    {
        "name": "delete all -> looks tasks up first",
        "text": "Delete all my leisure tasks",
        "tool": "list_tasks",
        "check": None,
    },
    {
        "name": "change by name -> looks task up first",
        "text": "Change the plumber task urgency to high",
        "tool": "list_tasks",
        "check": None,
    },
    {
        "name": "greeting -> no tool",
        "text": "hello",
        "tool": None,
        "check": None,
    },
    {
        "name": "off topic -> no tool",
        "text": "What is the capital of France?",
        "tool": None,
        "check": None,
    },
]


def timed(fn, messages, tools):
    started = time.perf_counter()
    response = fn(messages, tools)
    return response, time.perf_counter() - started


def usage_text(response) -> str:
    usage = getattr(response, "usage", None)
    return (
        f"prompt={getattr(usage, 'prompt_tokens', None)} "
        f"completion={getattr(usage, 'completion_tokens', None)}"
    )



def run_plain(fn):
    messages = [{"role": "user", "content": "Reply with the single word: ready"}]
    response, seconds = timed(fn, messages, None)
    text = (response.choices[0].message.content or "").strip()
    ok = bool(text)
    return ok, f"{seconds:.2f}s {usage_text(response)} reply={text[:60]!r}"


def run_case(fn, case):
    messages = BASE + [{"role": "user", "content": case["text"]}]
    response, seconds = timed(fn, messages, TOOLS)
    msg = response.choices[0].message
    calls = msg.tool_calls or []

    name = calls[0].function.name if calls else None
    args = {}

    if calls:
        try:
            args = json.loads(calls[0].function.arguments or "{}")
        except json.JSONDecodeError:
            return False, f"{seconds:.2f}s tool arguments are not valid JSON: {calls[0].function.arguments!r}"

    ok = name == case["tool"]

    if ok and case["check"] is not None:
        ok = bool(case["check"](args))

    if ok and case["tool"] is None:
        ok = bool((msg.content or "").strip())

    shown = f"tool={name} args={args}" if calls else f"no tool, reply={(msg.content or '')[:80]!r}"
    return ok, f"{seconds:.2f}s {usage_text(response)} {shown}"


def run_roundtrip(fn):
    """tool call -> fake result sent back -> final plain-text answer."""
    fake_id = "task-9f3a1c"
    messages = BASE + [{"role": "user", "content": "What tasks do I have in Work?"}]

    response, first = timed(fn, messages, TOOLS)
    msg = response.choices[0].message

    if not msg.tool_calls:
        return False, f"{first:.2f}s expected a tool call, got reply={(msg.content or '')[:80]!r}"

    messages.append(message_to_dict(msg))

    fake_result = [
        {
            "id": fake_id,
            "title": "Finalize the client demo slides",
            "section": "work",
            "has_explicit_time": False,
            "deadline": "2026-10-13T17:00:00+05:30",
        }
    ]

    for tc in msg.tool_calls:
        messages.append(
            {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(fake_result)}
        )

    response2, second = timed(fn, messages, TOOLS)
    final = (response2.choices[0].message.content or "").strip()
    again = response2.choices[0].message.tool_calls

    problems = []
    if again:
        problems.append("called another tool instead of answering")
    if not final:
        problems.append("empty final reply")
    if "slides" not in final.lower():
        problems.append("reply does not mention the task")
    if fake_id in final:
        problems.append("raw task id leaked into the reply")
    if "**" in final or "`" in final:
        problems.append("markdown in the reply")

    detail = f"{first:.2f}s + {second:.2f}s reply={final[:100]!r}"
    if problems:
        detail += "  PROBLEMS: " + "; ".join(problems)

    return not problems, detail


def run_all(label, fn) -> int:
    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)

    tests = [("plain reply (no tools)", lambda: run_plain(fn))]
    tests += [(case["name"], (lambda c=case: run_case(fn, c))) for case in CASES]
    tests.append(("tool call -> result -> final answer", lambda: run_roundtrip(fn)))

    passed = 0

    for name, test in tests:
        try:
            ok, detail = test()
        except Exception as exc:
            ok, detail = False, f"ERROR {type(exc).__name__}: {str(exc)[:400]}"

        passed += int(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] {name}\n       {detail}")
        time.sleep(PAUSE_SECONDS)

    print(f"\n{passed}/{len(tests)} passed")
    return passed


def main():
    if not PRIMARY_ENABLED:
        print(
            "Primary provider is not configured. Set AGENT_PROVIDER, AGENT_MODEL and "
            "AGENT_API_KEY in backend/.env and run again."
        )
        return 1

    run_all(f"PRIMARY  {PROVIDER}  model={PRIMARY_MODEL}", call_primary)

    if "--compare" in sys.argv:
        run_all("BASELINE  groq  model=openai/gpt-oss-120b", call_groq)

    return 0


if __name__ == "__main__":
    sys.exit(main())
