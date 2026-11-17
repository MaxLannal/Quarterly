"""Agent A4: the moderation classifier (SPEC "A4. Moderation").

Students' posts and comments are NOT checked before they are published (Richard, 2026-11-14,
OPEN_QUESTIONS P08-1): they go up at once after the email/phone scrub, and anything that breaks
the guidelines is taken down through reports and the admin moderation queue. A4 now labels
only the AI-written "What students say" summaries (`api.attributes.a3`), which publish only
on `ok`.

The classifier holds no tools at all, reads the text only inside `<untrusted_source>`, and its
answer is one label from a closed set: forum text cannot make it do anything but pick a label.
When it cannot answer (no client, an error, a malformed answer, or no answer within 3 seconds)
`classify` returns None and the summary is not published.

`decide` turns a label into the note an author sees; it is kept for posts that an earlier
version of the forum held or rejected.
"""

from __future__ import annotations

import html
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from llm_gateway.api import LLM, Message
from pydantic import BaseModel

log = logging.getLogger(__name__)

TASK = "a4_moderation"
PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts" / "a4_moderation.md"
#: Wall-clock budget for one classification (prompt 08: "3 s timeout -> hold for review").
TIMEOUT_S = 3.0

Label = Literal[
    "ok",
    "personal_attack",
    "identifying_info",
    "harassment",
    "sexual",
    "misconduct_claim",
    "spam",
    "off_topic",
]
HOLD_LABELS = frozenset({"identifying_info", "misconduct_claim"})
REJECT_LABELS = frozenset({"personal_attack", "harassment", "sexual", "spam", "off_topic"})

#: What the author sees. Fixed text, never the model's words.
LABEL_TEXT: dict[str, str] = {
    "personal_attack": "it reads as a personal attack",
    "identifying_info": "it may identify a person",
    "harassment": "it reads as harassment",
    "sexual": "it contains sexual content",
    "misconduct_claim": "it makes a claim of misconduct (report those to the University)",
    "spam": "it looks like spam",
    "off_topic": "it is not about this course or its teaching",
}
UNAVAILABLE = "classifier_unavailable"


class A4Label(BaseModel):
    """The classifier's whole answer."""

    label: Label


@dataclass(frozen=True)
class Decision:
    status: Literal["visible", "held", "removed"]
    #: The label, or `classifier_unavailable`; None for a clean `ok`.
    reason: str | None
    #: Shown to the author only.
    note: str | None


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str


@lru_cache(maxsize=1)
def load_prompt(path: Path = PROMPT_PATH) -> Prompt:
    """`prompts/a4_moderation.md`: a `---` header with `version:`, then the system prompt."""
    text = path.read_text(encoding="utf-8")
    _, header, body = text.split("---", 2)
    fields = dict(line.split(":", 1) for line in header.strip().splitlines() if ":" in line)
    return Prompt(version=fields["version"].strip(), system=body.strip())


def wrap_untrusted(text: str, source_id: str) -> str:
    """The text as data: inside `<untrusted_source>`, with any closing tag it contains
    defused so it cannot end the block early."""
    safe = html.escape(text, quote=False)  # no tag inside, in any letter case
    return f'<untrusted_source id="{source_id}">\n{safe}\n</untrusted_source>'


_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="a4-moderation")


def classify(llm: LLM, text: str, *, source_id: str) -> Label | None:
    """The A4 label, or None when the classifier could not answer in time."""
    try:
        prompt = load_prompt()
    except (OSError, ValueError, KeyError):
        log.warning("a4 moderation prompt missing or malformed")
        return None
    future = _executor.submit(
        llm.structured,
        TASK,
        system=prompt.system,
        messages=[Message(role="user", content=wrap_untrusted(text, source_id))],
        schema=A4Label,
        prompt_version=prompt.version,
        timeout_s=TIMEOUT_S,
    )
    try:
        answer = future.result(timeout=TIMEOUT_S)
    except FutureTimeout:
        future.cancel()
        log.warning("a4 moderation timed out; holding for review")
        return None
    except Exception as exc:  # LLMUnavailableError, validation errors, anything else
        # The exception type only: messages may quote the text.
        log.warning("a4 moderation unavailable (%s); holding for review", type(exc).__name__)
        return None
    return answer.label if isinstance(answer, A4Label) else None


def decide(label: Label | None) -> Decision:
    if label is None:
        return Decision(
            "held",
            UNAVAILABLE,
            "Held for review: the automatic check is unavailable, so a moderator will read it.",
        )
    if label == "ok":
        return Decision("visible", None, None)
    if label in HOLD_LABELS:
        return Decision("held", label, f"Held for a moderator because {LABEL_TEXT[label]}.")
    return Decision(
        "removed",
        label,
        f"Not published because {LABEL_TEXT[label]}. "
        "If you think this is a mistake, ask for human review.",
    )
