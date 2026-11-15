"""Checks on parsed sections (SPEC "Quarterly schedule pipeline", step 2).

- **Instructor names.** A name matches an instructor only when it is the same name after
  normalising (case, punctuation, accents, "Last, First" order) or equals one of their
  aliases. A name *similar* to someone (score >= `UNCERTAIN_AT`) is never merged by itself:
  it goes to review. Distinct people often differ by one letter ("Demo Instructor A" and
  "Demo Instructor B" score 0.94), so no score is high enough to merge automatically. A name
  unlike anyone becomes a new instructor.
- **Section counts.** Per subject, this term's count must stay within +/-30% of the same
  quarter last year; otherwise an alert goes to review. No baseline -> no alert.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

#: Similarity at or above which an unmatched name is treated as "maybe the same person".
UNCERTAIN_AT = 0.80
COUNT_TOLERANCE = 0.30


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    if text.count(",") == 1:  # "Last, First" -> "First Last"
        last, first = (p.strip() for p in text.split(","))
        text = f"{first} {last}"
    text = re.sub(r"[^\w\s-]", " ", text.lower())
    return " ".join(text.replace("-", " ").split())


def similarity(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    direct = SequenceMatcher(None, na, nb).ratio()
    tokens = SequenceMatcher(None, " ".join(sorted(na.split())), " ".join(sorted(nb.split())))
    return max(direct, tokens.ratio())


@dataclass(frozen=True)
class KnownInstructor:
    id: int
    display_name: str
    aliases: tuple[str, ...] = ()

    def names(self) -> tuple[str, ...]:
        return (self.display_name, *self.aliases)


@dataclass(frozen=True)
class NameMatch:
    name: str
    outcome: Literal["matched", "uncertain", "new"]
    instructor_id: int | None = None
    #: (instructor id, display name, score), best first; for review items.
    candidates: tuple[tuple[int, str, float], ...] = ()


def match_name(name: str, known: list[KnownInstructor]) -> NameMatch:
    key = sorted(normalize_name(name).split())  # the same words in any order
    for person in known:
        if any(sorted(normalize_name(n).split()) == key for n in person.names()):
            return NameMatch(name, "matched", person.id)
    scored = sorted(
        (
            (p.id, p.display_name, round(max(similarity(name, n) for n in p.names()), 3))
            for p in known
        ),
        key=lambda c: -c[2],
    )
    close = tuple(c for c in scored if c[2] >= UNCERTAIN_AT)[:5]
    if close:
        return NameMatch(name, "uncertain", candidates=close)
    return NameMatch(name, "new")


@dataclass(frozen=True)
class CountCheck:
    subject: str
    count: int
    baseline: int | None  # same quarter last year; None when there is no data
    baseline_term: str

    @property
    def change(self) -> float | None:
        if not self.baseline:
            return None
        return (self.count - self.baseline) / self.baseline

    @property
    def alert(self) -> bool:
        change = self.change
        return change is not None and abs(change) > COUNT_TOLERANCE + 1e-9


def same_quarter_last_year(term_id: str) -> str:
    year, quarter = term_id.split("-")
    return f"{int(year) - 1}-{quarter}"
