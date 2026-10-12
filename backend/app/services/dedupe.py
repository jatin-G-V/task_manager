"""
Duplicate / part-of detection for new tasks.

Two steps, so the common case (nothing could be related) costs no extra LLM call:

  1. shortlist(): cheap rules pick the open tasks that could be related
                  (same day, either task has no date, or near-identical title)
  2. judge():     ONE small, focused LLM call decides: duplicate / part_of / none

Why a separate judge instead of asking the big task parser: a tiny prompt with
clear definitions and numbered candidates is far more reliable than one extra
field at the end of a 7,000-token parsing prompt, and it keeps the parser fast.
"""

import json
import logging
import re
from typing import Optional

from rapidfuzz import fuzz

from app.services.groq_client import groq_client
from app.services.taskfmt import when_text
from app.services.timeutil import to_local


logger = logging.getLogger(__name__)

# Change this if you have a faster model you trust for classification.
JUDGE_MODEL = "openai/gpt-oss-120b"

MAX_CANDIDATES = 8

# words that carry no meaning for "is this the same activity?"
_STOP = {
    "a", "an", "the", "to", "for", "at", "on", "in", "of", "and", "my", "i",
    "me", "go", "going", "do", "get", "some", "need", "want", "have", "tonight",
    "today", "tomorrow", "pm", "am", "task", "add",
}


def _words(text) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    return " ".join(sorted(w for w in cleaned.split() if w not in _STOP))


def _anchor(task: dict):
    value = task.get("scheduled_start") or task.get("deadline")
    return to_local(value) if value else None


def shortlist(parsed: dict, open_tasks: list) -> list:
    """Open tasks that could be related to the new one (best first, at most 8)."""
    new_words = _words(parsed.get("title"))
    new_when = _anchor(parsed)

    scored = []

    for task in open_tasks:
        old_when = _anchor(task)

        # A task without a date can belong to any day (for example an undated
        # "Buy groceries" and a new "Buy milk tomorrow"), so it stays a candidate.
        same_day = (
            new_when is None
            or old_when is None
            or new_when.date() == old_when.date()
        )

        old_words = _words(task.get("title"))
        score = (
            fuzz.token_set_ratio(new_words, old_words)
            if new_words and old_words
            else 0
        )

        # same day / undated -> always worth a look; other days -> only near-identical titles
        if same_day or score >= 85:
            scored.append((not same_day, -score, task))

    scored.sort(key=lambda item: (item[0], item[1]))

    return [task for _, _, task in scored[:MAX_CANDIDATES]]


JUDGE_PROMPT = """You help a task app avoid clutter. Decide whether a NEW task is related to one EXISTING open task.

Relations:
- duplicate: the NEW task is the same activity as the existing one, so keeping both would be redundant. Different wording is still a duplicate:
  "go shopping at the mall at 9pm" vs "go to mall for shopping tonight"
  "buy milk tonight" vs "buy milk"
- part_of: the NEW task is one small item or step that naturally belongs inside the broader existing task:
  "buy milk" inside "buy groceries"; "book hotel" inside "plan Goa trip".
- null: everything else. A different person, client, place or activity is NOT related. Sharing only the time of day is NOT related. If unsure, answer null.

A vague time ("tonight", "today") and a clock time on the same day can belong to the same plan.

Answer with JSON only: {"index": <number of the existing task or null>, "relation": "duplicate" | "part_of" | null}"""


def judge(parsed: dict, candidates: list) -> Optional[dict]:
    """Returns {"task": <existing task>, "relation": "duplicate" | "part_of"} or None.

    Fails open: if the model call breaks, the task is simply created.
    """
    if not candidates:
        return None

    lines = "\n".join(
        f"{i} | {c.get('title')} | {when_text(c) or 'no date'}"
        for i, c in enumerate(candidates, 1)
    )

    user = (
        f"NEW: {parsed.get('title')} | {when_text(parsed) or 'no date'}\n"
        f"EXISTING:\n{lines}"
    )

    try:
        response = groq_client.chat.completions.create(
            model=JUDGE_MODEL,
            response_format={"type": "json_object"},
            temperature=0,
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        data = json.loads(response.choices[0].message.content)

    except Exception:
        logger.exception("dedupe judge failed; treating as no match")
        return None

    if not isinstance(data, dict):
        return None

    index = data.get("index")
    relation = data.get("relation")

    if (
        relation not in ("duplicate", "part_of")
        or not isinstance(index, int)
        or isinstance(index, bool)
        or not 1 <= index <= len(candidates)
    ):
        return None

    logger.info(
        "DEDUPE new=%r matched=%r relation=%s",
        parsed.get("title"),
        candidates[index - 1].get("title"),
        relation,
    )

    return {"task": candidates[index - 1], "relation": relation}