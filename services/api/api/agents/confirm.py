"""Typed confirmations in the advisor chat (SPEC "A2. Advisor chat"): a deterministic parser,
never a model.

Two forms are accepted, case-insensitive, with an optional final period or "!":

- an **affirmation** of the latest proposal: "apply it", "apply", "apply this", "apply the
  change(s)", "apply the proposal", "yes, apply it", "I agree", "I agree, apply it",
  "confirm", "I confirm";
- an **explicit command**: "I agree to" followed by actions joined by "and", "," or ";":
    - `add <codes> to|into|in <term>`
    - `move <codes> [from <term>] to|into|in <term>`
    - `remove <codes> [from|in <term>]`
  where `<codes>` is one or more course codes ("MATH 20700", "math20700", "MATH-20700")
  joined by "and" or ",", and `<term>` is "Autumn 2027" / "Fall 2027" / "Aut 2027"
  (also Winter, Spring, Summer, with an optional "quarter"), a term id "2027-AU", or a plan
  year "Autumn Y2" / "Y2 Autumn" / "Y2-AU" / "Autumn of year 2". One verb may cover several
  groups: "add MATH 20700 to Autumn 2027 and CMSC 27100 to Winter 2028".

Anything else (another word, a missing term, a code in the wrong place) is not a
confirmation. The server applies parsed operations only if they equal the latest proposal's
operations or are fully explicit, and only while the plan still has the proposal's hash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import cast

from planner_core.models import AddOp, ChangeOp, MoveOp, Quarter, RemoveOp
from planner_core.terms import term_at

_AFFIRM = re.compile(
    r"^(?:(?:yes|ok|okay)[,!.]?\s+)?(?:please\s+)?"
    r"(?:apply(?:\s+(?:it|this|that|the\s+(?:change|changes|proposal|proposed\s+change)))?"
    r"|i\s+agree(?:,?\s+apply\s+it)?|i\s+confirm|confirm)"
    r"(?:,?\s+please)?$"
)
_PREFIX = re.compile(r"^i\s+agree\s+to\s+")

_QUARTERS: dict[str, Quarter] = {
    "autumn": "AU",
    "fall": "AU",
    "aut": "AU",
    "au": "AU",
    "winter": "WI",
    "win": "WI",
    "wi": "WI",
    "spring": "SP",
    "spr": "SP",
    "sp": "SP",
    "summer": "SU",
    "sum": "SU",
    "su": "SU",
}
_Q = r"(autumn|fall|aut|winter|win|spring|spr|summer|sum)"
_QID = r"(au|wi|sp|su)"

# Each token pattern is tried at the current position, in order.
_TOKENS: list[tuple[str, re.Pattern[str]]] = [
    ("SEP", re.compile(r"(?:,\s*and\b|,|;|\band\b)")),
    ("VERB", re.compile(r"\b(add|move|remove)\b")),
    ("FROM", re.compile(r"\bfrom\b")),
    ("TO", re.compile(r"\b(to|into)\b")),
    ("IN", re.compile(r"\bin\b")),
    ("TERM_ID", re.compile(r"\b(\d{4})-" + _QID + r"\b")),
    ("TERM_REL", re.compile(r"\by([1-9])[\s-]?" + _QID + r"\b")),
    ("TERM_REL", re.compile(r"\by([1-9])\s+" + _Q + r"(?:\s+quarter)?\b")),
    ("TERM_REL_Q", re.compile(_Q + r"(?:\s+quarter)?\s+(?:of\s+)?(?:y|year\s+)([1-9])\b")),
    ("TERM_ABS", re.compile(_Q + r"(?:\s+quarter)?\s+(\d{4})\b")),
    ("CODE", re.compile(r"\b([a-z]{2,5})[\s-]?(\d{5})\b")),
]


@dataclass(frozen=True)
class Confirmation:
    #: True for "apply it": the latest proposal, whatever its operations.
    affirm: bool
    ops: list[ChangeOp] = field(default_factory=list)


class _NoParseError(Exception):
    pass


def _clean(text: str) -> str:
    text = " ".join(text.strip().lower().replace(chr(0x2019), "'").split())
    return text.rstrip(".!").strip()


def _tokens(text: str, entry_term: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        for kind, pattern in _TOKENS:
            m = pattern.match(text, i)
            if m is None:
                continue
            if kind == "CODE":
                out.append(("CODE", f"{m.group(1).upper()} {m.group(2)}"))
            elif kind == "TERM_ID":
                out.append(("TERM", f"{m.group(1)}-{m.group(2).upper()}"))
            elif kind == "TERM_REL":
                year, q = m.group(1), m.group(2)
                out.append(("TERM", term_at(entry_term, int(year), _QUARTERS[q])))
            elif kind == "TERM_REL_Q":
                q, year = m.group(1), m.group(2)
                out.append(("TERM", term_at(entry_term, int(year), _QUARTERS[q])))
            elif kind == "TERM_ABS":
                q, year = m.group(1), m.group(2)
                out.append(("TERM", f"{year}-{_QUARTERS[q]}"))
            elif kind == "VERB":
                out.append(("VERB", m.group(1)))
            else:
                out.append((kind, m.group(0)))
            i = m.end()
            break
        else:
            raise _NoParseError(text[i:])
    return out


@dataclass
class _Group:
    verb: str
    codes: list[str] = field(default_factory=list)
    from_term: str | None = None
    to_term: str | None = None
    in_term: str | None = None

    @property
    def has_term(self) -> bool:
        return any((self.from_term, self.to_term, self.in_term))

    def ops(self) -> list[ChangeOp]:
        if not self.codes:
            raise _NoParseError("no course")
        out: list[ChangeOp] = []
        for code in self.codes:
            if self.verb == "add":
                term = self.to_term or self.in_term
                if term is None or self.from_term is not None:
                    raise _NoParseError("add needs one target quarter")
                out.append(AddOp(course=code, term=term))
            elif self.verb == "move":
                target = self.to_term or self.in_term
                if target is None or (self.to_term and self.in_term):
                    raise _NoParseError("move needs a target quarter")
                out.append(MoveOp(course=code, from_term=self.from_term, to_term=target))
            else:
                if self.to_term is not None or (self.from_term and self.in_term):
                    raise _NoParseError("remove takes at most one quarter")
                out.append(RemoveOp(course=code, term=self.from_term or self.in_term))
        return out


def _explicit(body: str, entry_term: str) -> list[ChangeOp]:
    tokens = _tokens(body, entry_term)
    if not tokens or tokens[0][0] != "VERB":
        raise _NoParseError("must start with add, move or remove")
    groups: list[_Group] = []
    current: _Group | None = None
    i = 0
    while i < len(tokens):
        kind, value = tokens[i]
        if kind == "VERB":
            current = _Group(value)
            groups.append(current)
        elif kind == "CODE":
            assert current is not None
            if current.has_term:  # "add A to X and B to Y": a new group, same verb
                current = _Group(current.verb)
                groups.append(current)
            current.codes.append(value)
        elif kind in ("FROM", "TO", "IN"):
            assert current is not None
            if i + 1 >= len(tokens) or tokens[i + 1][0] != "TERM" or not current.codes:
                raise _NoParseError(f"{value} needs a quarter after a course")
            slot = {"FROM": "from_term", "TO": "to_term", "IN": "in_term"}[kind]
            if getattr(current, slot) is not None:
                raise _NoParseError("quarter given twice")
            setattr(current, slot, tokens[i + 1][1])
            i += 1
        elif kind == "TERM":
            raise _NoParseError("a quarter needs 'to', 'in' or 'from' before it")
        elif kind == "SEP" and (
            i + 1 >= len(tokens) or tokens[i + 1][0] == "SEP" or tokens[i - 1][0] == "VERB"
        ):
            raise _NoParseError("dangling separator")
        i += 1
    return [op for g in groups for op in g.ops()]


def parse_confirmation(text: str, entry_term: str) -> Confirmation | None:
    """The confirmation `text` expresses, or None if it is not one."""
    cleaned = _clean(text)
    if _AFFIRM.match(cleaned):
        return Confirmation(affirm=True)
    m = _PREFIX.match(cleaned)
    if m is None:
        return None
    try:
        ops = _explicit(cleaned[m.end() :], entry_term)
    except (_NoParseError, ValueError):
        return None
    return Confirmation(affirm=False, ops=ops) if ops else None


def fully_explicit(ops: list[ChangeOp]) -> bool:
    """Every operation names its course and every quarter it touches."""
    for op in ops:
        if op.op in ("lock", "unlock") or getattr(op, "course", None) is None:
            return False
        if isinstance(op, MoveOp) and op.from_term is None:
            return False
        if isinstance(op, RemoveOp) and op.term is None:
            return False
    return True


def _matches(typed: ChangeOp, proposed: ChangeOp) -> bool:
    if typed.op != proposed.op:
        return False
    if isinstance(proposed, AddOp):
        p = proposed
        t = cast(AddOp, typed)
        defaults = (
            p.slot_ref is None
            and p.status == "planned"
            and p.units is None
            and p.grading == "letter"
            and not p.locked
        )
        return defaults and p.course == t.course and p.term == t.term
    if getattr(proposed, "item_id", None) is not None or getattr(proposed, "slot_ref", None):
        return False
    if getattr(proposed, "course", None) != getattr(typed, "course", None):
        return False
    if isinstance(proposed, MoveOp):
        t_move = cast(MoveOp, typed)
        return proposed.to_term == t_move.to_term and t_move.from_term in (
            None,
            proposed.from_term,
        )
    if isinstance(proposed, RemoveOp):
        t_rem = cast(RemoveOp, typed)
        return t_rem.term in (None, proposed.term)
    return False


def ops_equal(typed: list[ChangeOp], proposed: list[ChangeOp]) -> bool:
    """The typed operations are exactly the proposal's (in any order). A quarter the student
    leaves out of "move ... to" or "remove ..." matches the proposal's."""
    if len(typed) != len(proposed):
        return False
    left = list(proposed)
    for op in typed:
        hit = next((p for p in left if _matches(op, p)), None)
        if hit is None:
            return False
        left.remove(hit)
    return True


HELP = (
    "To apply a change, click Apply on the proposal card, or type an exact confirmation such "
    'as "I agree to add MATH 20700 to Autumn 2027" or "apply it".'
)
