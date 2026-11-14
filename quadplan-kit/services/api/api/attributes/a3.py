"""Agent A3 (SPEC "A3. Forum -> attributes"): text extraction, "What students say"
summaries and cold-start estimates. Every LLM answer is checked by code before it is used:

- **Extraction:** each item carries a quote that must appear in the post. A workload number is
  accepted only if its quote contains that number. Difficulty cues map to the 1-5 scale
  (easy 2, moderate 3, hard 4, very hard 5).
- **Summary:** at most 120 words; every `[n]` marker must point into the citation list, and
  every cited id must be one of the posts the model was given. The summary must also get the
  A4 label `ok` from the moderation classifier; if the classifier cannot answer, it is not
  published.
- **Cold start:** workload 0-60 hours and difficulty 1-5 from the description and course
  level, labelled as an estimate.

Post text is untrusted: it goes to the model inside `<untrusted_source>` tags, and these calls
hold no tools at all.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from llm_gateway.api import LLM, Message
from pydantic import BaseModel, Field

from api.forum.moderation import classify, wrap_untrusted

PROMPTS = Path(__file__).resolve().parents[4] / "prompts"
SUMMARY_WORDS = 120
DIFFICULTY = {"easy": 2.0, "moderate": 3.0, "hard": 4.0, "very_hard": 5.0}


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str


def load_prompt(name: str) -> Prompt:
    """`prompts/<name>.md`: a `---` header with `version:`, then the system prompt."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    _, header, body = text.split("---", 2)
    fields = dict(line.split(":", 1) for line in header.strip().splitlines() if ":" in line)
    return Prompt(version=fields["version"].strip(), system=body.strip())


# ----------------------------------------------------------------------- extraction


class WorkloadMention(BaseModel):
    hours: float = Field(ge=0, le=100)
    quote: str


class DifficultyCue(BaseModel):
    level: Literal["easy", "moderate", "hard", "very_hard"]
    quote: str


class Note(BaseModel):
    text: str = Field(max_length=300)
    quote: str


class Extraction(BaseModel):
    workload_mentions: list[WorkloadMention] = []
    difficulty_cues: list[DifficultyCue] = []
    exam_style: list[Note] = []
    prerequisite_advice: list[Note] = []


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _in_post(quote: str, post: str) -> bool:
    # The model reads the post HTML-escaped (`wrap_untrusted`), so "<5 hrs" may come back as
    # "&lt;5 hrs".
    quote = _norm(html.unescape(quote))
    return bool(quote) and quote in _norm(post)


def _number_in(value: float, quote: str) -> bool:
    numbers = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", quote)}
    return value in numbers


def checked_extraction(raw: Extraction, post: str) -> Extraction:
    """Keep only items whose quote is in the post, and numbers that their quote contains."""
    return Extraction(
        workload_mentions=[
            w
            for w in raw.workload_mentions
            if _in_post(w.quote, post) and _number_in(w.hours, w.quote)
        ],
        difficulty_cues=[d for d in raw.difficulty_cues if _in_post(d.quote, post)],
        exam_style=[n for n in raw.exam_style if _in_post(n.quote, post)],
        prerequisite_advice=[n for n in raw.prerequisite_advice if _in_post(n.quote, post)],
    )


def extract(llm: LLM, post_id: int, text: str) -> Extraction:
    prompt = load_prompt("a3_extraction")
    raw = llm.structured(
        "a3_forum_extraction",
        system=prompt.system,
        messages=[Message("user", wrap_untrusted(text, f"post-{post_id}"))],
        schema=Extraction,
        prompt_version=prompt.version,
        timeout_s=30,
    )
    return checked_extraction(raw, text)


# -------------------------------------------------------------------------- summary


class Summary(BaseModel):
    text: str
    citations: list[int] = Field(default_factory=list)


class SummaryRejectedError(ValueError):
    """The summary broke a rule; it is not published."""


def checked_summary(raw: Summary, post_ids: set[int]) -> Summary:
    words = len(raw.text.split())
    if words == 0 or words > SUMMARY_WORDS:
        raise SummaryRejectedError(f"the summary has {words} words (1-{SUMMARY_WORDS} allowed)")
    if not raw.citations:
        raise SummaryRejectedError("the summary cites no post")
    unknown = [c for c in raw.citations if c not in post_ids]
    if unknown:
        raise SummaryRejectedError(f"the summary cites posts it was not given: {unknown}")
    markers = {int(n) for n in re.findall(r"\[(\d+)\]", raw.text)}
    if not markers or any(n < 1 or n > len(raw.citations) for n in markers):
        raise SummaryRejectedError("a [n] marker does not match the citation list")
    return raw


def summarize(llm: LLM, posts: list[tuple[int, str]]) -> Summary:
    """Write, check and moderate a summary; raises SummaryRejectedError when it may not be
    published (and LLMUnavailableError when there is no model)."""
    prompt = load_prompt("a3_summary")
    body = "\n\n".join(wrap_untrusted(text, str(post_id)) for post_id, text in posts)
    raw = llm.structured(
        "a3_forum_summary",
        system=prompt.system,
        messages=[Message("user", body)],
        schema=Summary,
        prompt_version=prompt.version,
        timeout_s=60,
    )
    summary = checked_summary(raw, {post_id for post_id, _ in posts})
    label = classify(llm, summary.text, source_id="summary")
    if label != "ok":
        raise SummaryRejectedError(
            f"moderation did not pass the summary ({label or 'unavailable'})"
        )
    return summary


# ------------------------------------------------------------------------ cold start


class ColdStart(BaseModel):
    workload_hours: float = Field(ge=0, le=60)
    difficulty: float = Field(ge=1, le=5)
    reason: str = Field(max_length=300)


def cold_start(llm: LLM, code: str, title: str, description: str | None) -> ColdStart:
    prompt = load_prompt("a3_cold_start")
    level = f"{code.split(' ')[1][:1]}0000"
    text = f"Course: {code} {title}\nLevel: {level}\n\n{description or '(no description)'}"
    return llm.structured(
        "a3_cold_start_estimate",
        system=prompt.system,
        messages=[Message("user", wrap_untrusted(text, code))],
        schema=ColdStart,
        prompt_version=prompt.version,
        timeout_s=30,
    )
