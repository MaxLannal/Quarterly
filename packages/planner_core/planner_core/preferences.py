"""Default course preferences for the plan generator, used when no agent ranked the courses
(SPEC "A1. Plan generator", fallback of step 3): interest-tag match first, then the forum
`recommend_rate`, then course level (lower first).

A preference is an integer; the order is lexicographic by construction:
- 10000 when the course matches an interest (a tag, a Core area or a word of its title);
- 100 per percentage point of `recommend_rate` (0..1, or 0..100 read as a percentage), so the
  rate alone never outweighs an interest match;
- up to 99 from the level (10000-level highest, 40000 and above lowest), which only breaks
  ties between equal rates.
"""

from __future__ import annotations

from collections.abc import Iterable

from planner_core.index import Index

INTEREST = 10000
RECOMMEND = 100  # per percentage point
LEVEL = 99
MAX_PREFERENCE = INTEREST + 100 * RECOMMEND + LEVEL


def interest_match(idx: Index, code: str, interests: Iterable[str]) -> bool:
    wanted = [i.strip().lower() for i in interests if i.strip()]
    if not wanted:
        return False
    course = idx.course(code)
    title = course.title.lower() if course is not None else ""
    tags = {t.lower() for t in idx.tags(code)}
    return any(interest in title or any(interest in tag for tag in tags) for interest in wanted)


def _recommend(idx: Index, code: str) -> float:
    value = idx.attribute(code, "recommend_rate")
    if value is None:
        return 0.0
    rate = value.value / 100 if value.value > 1 else value.value
    return max(0.0, min(1.0, rate))


def _level(code: str) -> int:
    number = int(code.split(" ")[1])
    return round(LEVEL * max(0, 40000 - number) / 30000) if number >= 10000 else LEVEL


def default_preference(idx: Index, code: str, interests: Iterable[str]) -> int:
    score = INTEREST if interest_match(idx, code, interests) else 0
    score += RECOMMEND * round(100 * _recommend(idx, code))
    return min(MAX_PREFERENCE, score + min(LEVEL, _level(code)))


def preferences(
    idx: Index,
    codes: Iterable[str],
    interests: Iterable[str],
    chosen: dict[str, int] | None = None,
) -> dict[str, int]:
    """Preference per code. `chosen` (an agent's 0..100 ranking) wins where it names a course:
    it maps to 10000..20000, above every unranked course that does not match an interest."""
    interests = list(interests)
    out: dict[str, int] = {}
    for code in codes:
        if chosen is not None and code in chosen:
            out[code] = INTEREST + 100 * max(0, min(100, chosen[code]))
        else:
            out[code] = default_preference(idx, code, interests)
    return out
