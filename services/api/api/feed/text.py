"""Plain-text helpers for the Catalog's browse rows: excerpts cut at whole words, whole-word
patterns for a student's interests, and markdown turned into plain text for quote snippets.
Deterministic and model-free. (The Feed's floating words, word clouds and headline topics went
with the Feed, issue #19.)"""

from __future__ import annotations

import html
import re

from api.forum.markdown import render_markdown
from api.forum.scrub import scrub

#: English function words plus the words every course description uses ("course", "students",
#: "topics"): none of them says what a course is about.
STOPWORDS = frozenset(
    """
    a about above across after again against all almost along also although always am among an
    and another any are around as at be became because become becomes been before being below
    between both but by can cannot could did do does doing done down during each either else
    enough especially even ever every few first for from further get gets given gives go going
    had has have having he her here hers him his how however i if in include includes including
    into is it its itself just last least less like made make makes making many may me might more
    most much must my near need needs neither never new next no nor not now of off often on once
    one only onto or other others otherwise our ours out over own part per perhaps put rather
    really same second see seen several shall she should since so some such take takes taken than
    that the their theirs them themselves then there these they third this those though three
    through throughout thus to together too toward towards two under until up upon us use used
    uses using very via was way ways we well were what whatever when where whether which while who
    whom whose why will with within without would yet you your yours
    course courses class classes student students studies study studying topic topics introduce
    introduces introduction introductory intro seminar seminars lecture lectures discussion
    discussions reading readings week weeks quarter quarters term terms year years focus focuses
    focused focusing examine examines examining explore explores exploring consider considers
    considering particular particularly special general basic basics advanced intermediate
    elementary beginning approaches approach issues issue questions question understanding
    understand provide provides providing offer offers offered emphasis emphasize various key
    major minor graduate undergraduate undergraduates prerequisite prerequisites consent instructor
    instructors required require requires requirement section sections credit credits unit units
    hours work works working paper papers assignment assignments project projects final exam
    exams midterm grade grades graded familiarity knowledge previous prior level levels area areas
    field fields both well part parts number open enrollment enroll enrolled limited permission
    i ii iii iv v vi etc vol learn learning learned
    able aim aims analyze analyzing apply applied aspect aspects available based begin begins
    better broad broadly central certain change changes chosen closely combine common complete
    completed concept concepts context contexts continue continues cover covers covered current
    deal deals depth describe develop developed developing different discuss discussed early
    effective engage engages engaging essential establish example examples explain extent
    familiar find following form forms foundation foundations fundamental fundamentals gain goal
    goals good great group groups help helps highly ideas important increasingly individual
    instance intended interest interested interests involve involved kind kinds known large later
    lead leading long look looking main material materials meet meets method methods mode modes
    multiple order overview perspective perspectives place play played plays point points possible
    practice practices present presents primary primarily range read real recent related relation
    relationship relationships result results role roles seek seeks sense sequence series sets
    short show significant simple simultaneously skill skills small specific specifically standard
    start strong subject subjects successful successfully taking theme themes time times today
    turn type types typically ultimately unique university upper usually value variety view views
    whole wide year-long quarter-long first-year second-year third-year fourth-year non-majors
    majors familiarity ability introduced covering also emphasizes highlight highlights students
    """.split()  # noqa: SIM905
)

_LETTER = "A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff\u0100-\u017e"
_WORD = re.compile(f"[{_LETTER}][{_LETTER}'\u2019-]*[{_LETTER}]")
_SPACE = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")
_BLOCK_TAGS = re.compile(r"</?(?:p|br|li|ul|ol|blockquote|pre|hr)\b[^>]*>")
_ROMAN = re.compile(r"^(?:i{1,3}|iv|v|vi{0,3}|ix|x)$", re.IGNORECASE)


def squash(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def excerpt(text: str | None, limit: int = 300) -> str:
    """`text` cut to at most `limit` characters at a word boundary, with an ellipsis if cut."""
    clean = squash(text or "")
    if len(clean) <= limit:
        return clean
    cut = clean[: limit - 1]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:-\u2013\u2014(") + "\u2026"


def plain_text(markdown: str) -> str:
    """A post or reply body as one line of plain text (markdown rendered, tags dropped, emails
    and phone numbers scrubbed)."""
    rendered = render_markdown(scrub(markdown))
    spaced = _BLOCK_TAGS.sub(" ", rendered)
    return squash(html.unescape(_TAGS.sub("", spaced)))


def words_of(text: str) -> list[str]:
    """The words of `text` (letters, inner apostrophes and hyphens), in order."""
    out = []
    for word in _WORD.findall(text):
        word = word.strip("'\u2019-")
        if word[-2:].lower() in ("'s", "\u2019s"):
            word = word[:-2]
        out.append(word)
    return out


def _usable(word: str) -> bool:
    low = word.lower()
    return len(low) >= 4 and low not in STOPWORDS and not _ROMAN.match(low)


def term_pattern(term: str) -> re.Pattern[str]:
    """A whole-word, case-insensitive pattern for an interest ("quantum computing" matches
    "Quantum  Computing" and "quantum computings"; "art" does not match "artificial")."""
    parts = [re.escape(p) for p in term.split()]
    return re.compile(r"\b" + r"[\s-]+".join(parts) + r"(?:s|es)?\b", re.IGNORECASE)


def significant_words(term: str) -> list[str]:
    """The words of an interest that carry meaning on their own ("the economics of cities" ->
    ["economics", "cities"])."""
    return [w for w in (x.lower() for x in words_of(term)) if _usable(w)]
