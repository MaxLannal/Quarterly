"""Deterministic Class Search parser: one saved results page -> sections.

The parser is driven by a `ParserConfig` (CSS selectors, see `scraper.dom`), so a layout
change is fixed by new selectors, which the self-repair agent may propose and a curator
approves. No code is ever generated.

IMPORTANT: `DEFAULT_CONFIG` matches the SYNTHETIC fixtures in `services/scraper/fixtures/`.
No real Class Search page has been seen yet (docs/OPEN_QUESTIONS.md, "Prompt 10"); the real
selectors will be written once Richard saves a few real result pages.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, field_validator

from scraper.dom import Node, SelectorError, parse_html, validate_selector

CODE_RE = re.compile(r"\b([A-Z]{4})\s*(\d{5})\b")
TIME_RE = re.compile(
    r"(?P<s>\d{1,2}:\d{2})\s*(?P<sa>[AaPp][Mm])?\s*[-\u2013]\s*(?P<e>\d{1,2}:\d{2})\s*(?P<ea>[AaPp][Mm])"
)
DAY_RE = re.compile(r"Th|Tu|Sa|Su|M|T|W|R|F|U|S")
DAY_NAMES = {
    "M": "Mon", "T": "Tue", "Tu": "Tue", "W": "Wed", "Th": "Thu", "R": "Thu", "F": "Fri",
    "Sa": "Sat", "S": "Sat", "Su": "Sun", "U": "Sun",
}  # fmt: skip
STATUSES = {
    "open": "open",
    "closed": "closed",
    "full": "closed",
    "wait list": "waitlist",
    "waitlist": "waitlist",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


class ParserConfig(BaseModel):
    """Selectors for one Class Search layout. Every field except `version` is a selector;
    the section fields are looked up inside one section row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    #: Must be present on every results page (proves the page is a results page).
    page_marker: str
    #: Present when a subject has no classes this term (zero rows is then not an error).
    empty_marker: str
    course_block: str
    course_code: str
    section_row: str
    section_no: str
    component: str
    instructors: str
    meetings: str
    location: str
    capacity: str
    status: str
    #: Separates several instructors in one cell.
    instructor_separator: str = ";"

    @field_validator(
        "page_marker",
        "empty_marker",
        "course_block",
        "course_code",
        "section_row",
        "section_no",
        "component",
        "instructors",
        "meetings",
        "location",
        "capacity",
        "status",
    )
    @classmethod
    def _selector(cls, value: str) -> str:
        try:
            validate_selector(value)
        except SelectorError as exc:
            raise ValueError(str(exc)) from exc
        return value


DEFAULT_CONFIG = ParserConfig(
    version="synthetic-1",
    page_marker="#class-search-results",
    empty_marker=".no-results",
    course_block="div.course-block",
    course_code=".course-code",
    section_row="tr.section-row",
    section_no="td.section",
    component="td.component",
    instructors="td.instructors",
    meetings="td.meetings",
    location="td.location",
    capacity="td.capacity",
    status="td.status",
)


@dataclass(frozen=True)
class ParsedSection:
    course_code: str
    section_no: str
    component: str | None
    instructors: tuple[str, ...]
    meetings: tuple[dict[str, object], ...]
    capacity: int | None
    status: str | None

    @property
    def subject(self) -> str:
        return self.course_code.split()[0]


class ParseError(ValueError):
    """The page does not fit the parser's layout (the schema check failed)."""


def _cell(row: Node, selector: str) -> str:
    node = row.select_one(selector)
    return node.text() if node is not None else ""


def parse_meetings(text: str, location: str = "") -> tuple[dict[str, object], ...]:
    """'MWF 10:30AM-11:20AM' -> [{days: [Mon, Wed, Fri], start: '10:30', end: '11:20'}].
    Several meetings are separated by ';'. 'TBA' or an empty cell -> no meetings."""
    out: list[dict[str, object]] = []
    for part in (p.strip() for p in text.split(";")):
        if not part or part.upper().startswith("TBA"):
            continue
        time = TIME_RE.search(part)
        if time is None:
            raise ParseError(f"cannot read meeting time {part!r}")
        days_text = part[: time.start()].strip().replace(" ", "")
        days = DAY_RE.findall(days_text)
        if not days or "".join(days) != days_text:
            raise ParseError(f"cannot read meeting days {part!r}")
        end_ampm = time.group("ea").upper()
        start_ampm = (time.group("sa") or end_ampm).upper()
        meeting: dict[str, object] = {
            "days": [DAY_NAMES[d] for d in days],
            "start": _to_24h(time.group("s"), start_ampm),
            "end": _to_24h(time.group("e"), end_ampm),
        }
        if location and location.upper() != "TBA":
            meeting["location"] = location
        out.append(meeting)
    return tuple(out)


def _to_24h(hhmm: str, ampm: str) -> str:
    hour, minute = (int(x) for x in hhmm.split(":"))
    if hour > 12 or minute > 59:
        raise ParseError(f"not a clock time: {hhmm}{ampm}")
    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def parse_capacity(text: str) -> int | None:
    """'34/80' (enrolled/limit) or '80' -> 80; empty -> None."""
    numbers = re.findall(r"\d+", text)
    if not text.strip():
        return None
    if not numbers:
        raise ParseError(f"cannot read capacity {text!r}")
    return int(numbers[-1])


def parse_status(text: str) -> str | None:
    key = " ".join(text.lower().split())
    if not key:
        return None
    if key not in STATUSES:
        raise ParseError(f"unknown section status {text!r}")
    return STATUSES[key]


def parse_page(html: str, config: ParserConfig = DEFAULT_CONFIG) -> list[ParsedSection]:
    """Every section on one results page. Raises `ParseError` when the page does not match
    the layout: no page marker, no course blocks without the empty marker, a block without a
    course code, a block without sections, or a cell that cannot be read."""
    root = parse_html(html)
    if root.select_one(config.page_marker) is None:
        raise ParseError(f"no results marker ({config.page_marker})")
    blocks = root.select(config.course_block)
    if not blocks:
        if root.select_one(config.empty_marker) is not None:
            return []
        raise ParseError(f"no course blocks ({config.course_block}) and no empty-page marker")
    out: list[ParsedSection] = []
    for block in blocks:
        code_text = _cell(block, config.course_code)
        code = CODE_RE.search(code_text)
        if code is None:
            raise ParseError(f"course block without a course code: {code_text[:60]!r}")
        course_code = f"{code.group(1)} {code.group(2)}"
        rows = block.select(config.section_row)
        if not rows:
            raise ParseError(f"{course_code}: no section rows ({config.section_row})")
        for row in rows:
            section_no = _cell(row, config.section_no)
            if not section_no:
                raise ParseError(f"{course_code}: a section row without a section number")
            names = _cell(row, config.instructors)
            instructors = tuple(
                n.strip()
                for n in names.split(config.instructor_separator)
                if n.strip() and n.strip().upper() not in {"TBA", "STAFF"}
            )
            out.append(
                ParsedSection(
                    course_code=course_code,
                    section_no=section_no,
                    component=_cell(row, config.component) or None,
                    instructors=instructors,
                    meetings=parse_meetings(
                        _cell(row, config.meetings), _cell(row, config.location)
                    ),
                    capacity=parse_capacity(_cell(row, config.capacity)),
                    status=parse_status(_cell(row, config.status)),
                )
            )
    keys = Counter((s.course_code, s.section_no, s.component) for s in out)
    dupes = [k for k, n in keys.items() if n > 1]
    if dupes:
        raise ParseError(f"duplicate sections on one page: {dupes[:3]}")
    return out
