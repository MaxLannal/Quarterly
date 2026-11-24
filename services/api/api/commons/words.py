"""The word limit of the AI answer under a Commons question (issue #20, D1 option A).

Richard chose a short AI answer under each question; the limit is 60 words, which he confirmed on
2026-11-24 "for now", to be tested in use (docs/OPEN_QUESTIONS.md F20-1). The prompt asks for
it, the submit tool rejects a longer answer once (the model gets one repair turn), and
`limit_words` clips anything longer that is stored or shown, so the limit holds even for answers
stored before it existed.

A word is what a reader sees: a run of characters between spaces that holds a letter or a digit.
Markdown bullets and dashes do not count; `[CMSC 14100](/courses/...)` counts two.
"""

from __future__ import annotations

import re

#: The most words an AI answer under a Commons question may have.
ANSWER_WORDS = 60

_TOKEN = re.compile(r"\S+")
_WORDLIKE = re.compile(r"[^\W_]")
_SENTENCE_END = re.compile(r"[.!?](?:\*\*|\*|_)?(?=\s|$)")
_TRAILING = " \t\n,;:(-" + "\N{EN DASH}\N{EM DASH}"


def count_words(text: str) -> int:
    return sum(1 for token in _TOKEN.finditer(text) if _WORDLIKE.search(token.group()))


def limit_words(text: str, limit: int = ANSWER_WORDS) -> str:
    """`text` with at most `limit` words. A longer text ends at its last full sentence inside the
    limit when that keeps at least half of it; otherwise it is cut after the limit-th word (or
    before a markdown link that the limit would split) and ends with "…". An open `**` is
    closed."""
    text = text.strip()
    words = [t for t in _TOKEN.finditer(text) if _WORDLIKE.search(t.group())]
    if len(words) <= limit:
        return text
    kept = text[: words[limit - 1].end()]
    link = kept.rfind("[")
    if link != -1 and "]" not in kept[link:]:
        kept = kept[:link]  # never end inside a link's text: the link would show as "[..."
    ends = [mt.end() for mt in _SENTENCE_END.finditer(kept)]
    if ends and count_words(kept[: ends[-1]]) >= limit // 2:
        kept = kept[: ends[-1]].rstrip()
    else:
        kept = kept.rstrip(_TRAILING) + "…"
    if kept.count("**") % 2:
        kept += "**"
    return kept
