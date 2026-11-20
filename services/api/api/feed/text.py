"""Plain-text helpers for the feed: excerpts cut at whole words, distinctive keywords of a course
(the page's floating words), word-cloud weights, short topics for the headline, and markdown
turned into plain text for comment snippets. Deterministic and model-free."""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Iterable

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
#: Where a long title can be cut into a topic ("Western Modern Art | from the Enlightenment").
_CUTS = "in of for on at through from to with since until before after across into between during"
_TOPIC_CUTS = frozenset(_CUTS.split())
_TAGS = re.compile(r"<[^>]+>")
_BLOCK_TAGS = re.compile(r"</?(?:p|br|li|ul|ol|blockquote|pre|hr)\b[^>]*>")
_ROMAN = re.compile(r"^(?:i{1,3}|iv|v|vi{0,3}|ix|x)$", re.IGNORECASE)
_TOPIC_PREFIXES = re.compile(
    r"^(?:an?\s+|the\s+)?(?:introduction|intro|introductory\s+topics|topics|seminar|readings|"
    r"studies|advanced\s+topics|special\s+topics|survey)\s+(?:to|in|on|of)\s+(?:the\s+)?",
    re.IGNORECASE,
)


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


def _floatable(word: str) -> bool:
    """A word worth floating: not hyphenated, not a long adverb ("ethnolinguistically"), not
    a subject code ("GREK")."""
    low = word.lower()
    if len(word) == 4 and word.isupper():
        return False
    return "-" not in low and not (len(low) > 7 and low.endswith("ly"))


#: Names and proper adjectives common in course titles, capitalised even when a description
#: does not show them in mid-sentence.
_NAMES = frozenset(
    """
    greek greece roman rome latin jewish judaism christian christianity islamic islam muslim
    arabic arab chinese china japanese japan korean korea indian india american america americas
    african africa european europe russian russia french france german germany italian italy
    spanish spain portuguese english hebrew persian iran iranian ottoman byzantine byzantium
    renaissance enlightenment reformation holocaust chicago shakespeare dante homer plato
    aristotle socrates bible biblical buddhist buddhism hindu hinduism sanskrit tibetan yiddish
    turkish mexican mexico caribbean atlantic pacific mediterranean asian asia latinx marx freud
    kant hegel nietzsche darwin einstein newton bach mozart beethoven tolstoy dostoevsky austen
    joyce woolf hollywood soviet anatolia egypt egyptian israel israeli palestine palestinian
    brazil brazilian andean maya aztec inca catholic protestant qur'an torah gospel jesus god
    python hilbert fourier bayesian euclidean riemann markov schrödinger hittite akkadian
    sumerian babylonian assyrian coptic armenian georgian ukrainian polish czech hungarian
    balkan balkans slavic scandinavian norse viking celtic irish scottish british britain
    victorian elizabethan harlem paris london athens venice florence berlin vienna moscow
    beijing tokyo kyoto delhi cairo jerusalem istanbul constantinople haiti haitian cuba cuban
    """.split()  # noqa: SIM905
)


def _proper(description: str | None) -> frozenset[str]:
    """Lowercased words to keep capitalised: known names, and words the description
    capitalises in mid-sentence ("Hilbert", "Flint")."""
    out: set[str] = set(_NAMES)
    for sentence in re.split(r"(?<=[.!?:;])\s+", description or ""):
        for word in words_of(sentence)[1:]:
            if word[0].isupper():
                out.add(word.lower())
    return frozenset(out)


def display_case(word: str, proper: frozenset[str]) -> str:
    """A word as the page shows it: acronyms and names keep their capitals, other words are
    lowercased ("Sexuality" -> "sexuality", "Greek" stays)."""
    if len(word) > 1 and word.isupper():
        return word
    return word if word.lower() in proper else word.lower()


def keywords(title: str, description: str | None, n: int = 8) -> list[str]:
    """6-10 distinctive words of a course, title words first: the words that float off its
    card. Names and acronyms keep their capitals; other words are lowercased."""
    scores: dict[str, float] = {}
    shown: dict[str, str] = {}
    order: dict[str, int] = {}
    for weight, text in ((4.0, title), (1.0, description or "")):
        for word in words_of(text):
            if not _usable(word) or not _floatable(word):
                continue
            low = word.lower()
            scores[low] = scores.get(low, 0.0) + weight + min(len(low), 12) / 24
            order.setdefault(low, len(order))
            if low not in shown or (shown[low][0].isupper() and not word[0].isupper()):
                shown[low] = word
    ranked = sorted(scores, key=lambda w: (-scores[w], order[w]))
    proper = _proper(description)
    out: list[str] = []
    for low in ranked:
        word = display_case(shown[low], proper)
        if any(low != o.lower() and (low in o.lower() or o.lower() in low) for o in out):
            continue  # "quantum" and "quantumlab" are one idea
        out.append(word)
        if len(out) >= n:
            break
    return out


def cloud(titles: Iterable[str], n: int = 28) -> list[tuple[str, int]]:
    """The `n` most frequent content words of `titles` with a weight from 1 to 5."""
    counts: Counter[str] = Counter()
    shown: dict[str, str] = {}
    for title in titles:
        for word in set(words_of(title)):
            if not _usable(word):
                continue
            low = word.lower()
            counts[low] += 1
            shown.setdefault(low, word if word.isupper() else low)
    top = counts.most_common(n)
    if not top:
        return []
    high, low_count = top[0][1], top[-1][1]
    span = max(high - low_count, 1)
    return [(shown[w], 1 + round(4 * (c - low_count) / span)) for w, c in top]


def _short(part: str) -> list[str]:
    part = _TOPIC_PREFIXES.sub("", part.strip()).strip()
    words = part.split()
    while words and _ROMAN.match(words[-1].strip(",.")):
        words.pop()
    return words


def topic(title: str, description: str | None = None) -> str:
    """A short topic for the headline, in running-text case: "Introduction to Quantum
    Computing" -> "quantum computing"; "Gender and Sexuality in World Civilizations I" ->
    "gender and sexuality"; the part after a colon when the part before it is long."""
    head, _, tail = title.partition(":")
    words = _short(head)
    if len(words) > 4 and tail and 1 <= len(_short(tail)) <= 4:
        words = _short(tail)
    if len(words) > 4:
        cut = next(
            (i for i, w in enumerate(words) if i >= 2 and w.lower() in _TOPIC_CUTS), len(words)
        )
        words = words[: min(cut, 5)]
    while words and words[-1].lower() in _TOPIC_CUTS | {"and", "the", "a", "an"}:
        words.pop()
    if len(words) > 1 and words[0].lower() in {"the", "a", "an"}:
        words = words[1:]
    proper = _proper(description)
    shown = [display_case(w.strip(",."), proper) for w in words]
    return " ".join(w for w in shown if w) or title


def term_pattern(term: str) -> re.Pattern[str]:
    """A whole-word, case-insensitive pattern for an interest ("quantum computing" matches
    "Quantum  Computing" and "quantum computings"; "art" does not match "artificial")."""
    parts = [re.escape(p) for p in term.split()]
    return re.compile(r"\b" + r"[\s-]+".join(parts) + r"(?:s|es)?\b", re.IGNORECASE)


def significant_words(term: str) -> list[str]:
    """The words of an interest that carry meaning on their own ("the economics of cities" ->
    ["economics", "cities"])."""
    return [w for w in (x.lower() for x in words_of(term)) if _usable(w)]
