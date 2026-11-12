"""Term arithmetic. Term ids are `<calendar year>-<quarter>`: Autumn 2026 is `2026-AU`, the
following Winter is `2027-WI`. An academic year runs AU, WI, SP, SU."""

from __future__ import annotations

from typing import cast

from planner_core.models import Quarter

#: Display order inside one academic year.
QUARTERS: tuple[Quarter, ...] = ("AU", "WI", "SP", "SU")
#: Chronological order inside one calendar year.
_CALENDAR_ORDER = {"WI": 0, "SP": 1, "SU": 2, "AU": 3}


def parse_term(term: str) -> tuple[int, Quarter]:
    year, quarter = term.split("-")
    if quarter not in _CALENDAR_ORDER or len(year) != 4 or not year.isdigit():
        raise ValueError(f"not a term id: {term!r}")
    return int(year), cast(Quarter, quarter)


def term_key(term: str) -> tuple[int, int]:
    """Sort key: chronological order."""
    year, quarter = parse_term(term)
    return year, _CALENDAR_ORDER[quarter]


def is_before(a: str, b: str) -> bool:
    return term_key(a) < term_key(b)


def academic_year(term: str) -> int:
    """The calendar year in which the term's academic year starts (2027-WI -> 2026)."""
    year, quarter = parse_term(term)
    return year if quarter == "AU" else year - 1


def year_index(term: str, entry_term: str) -> int:
    """1-based plan year of `term` for a student who entered in `entry_term`."""
    return academic_year(term) - academic_year(entry_term) + 1


def term_at(entry_term: str, year: int, quarter: Quarter) -> str:
    """The term id of `quarter` in plan year `year` (1-based)."""
    start = academic_year(entry_term) + year - 1
    return f"{start if quarter == 'AU' else start + 1}-{quarter}"


def resolve_term_ref(ref: str, entry_term: str) -> str:
    """`Y2-SP` -> absolute term id for this entry term; absolute ids pass through."""
    if ref.startswith("Y"):
        year, quarter = ref[1:].split("-")
        if quarter not in _CALENDAR_ORDER:
            raise ValueError(f"not a term reference: {ref!r}")
        return term_at(entry_term, int(year), cast(Quarter, quarter))
    parse_term(ref)
    return ref
