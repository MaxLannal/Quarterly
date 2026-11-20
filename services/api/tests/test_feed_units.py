"""The feed's pieces without a database: categories cover the catalog, the shelf is well formed,
the text helpers, the cursor, and the checks on the AI curator's notes."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from api.feed import categories as fcat
from api.feed import shelf
from api.feed import text as ftext
from api.feed.notes import NOTE_MAX, NotesAnswer, checked, fallback
from api.feed.service import Described, decode_cursor, default_headline, encode_cursor

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "seed" / "2026-27" / "courses"

#: Motifs the web page knows how to draw (apps/web/src/features/feed/art).
MOTIFS = {
    "arches", "lattice", "orbits", "circuit", "cells", "waves", "curves", "network", "columns",
    "scrolls", "pages", "glyphs", "notes", "tiles", "maps", "constellation", "frames",
}  # fmt: skip


def _seeded_subjects() -> set[str]:
    subjects: set[str] = set()
    for path in sorted(SEED.glob("*.yaml")):
        for course in yaml.safe_load(path.read_text())["courses"]:
            subjects.add(str(course["code"]).split()[0])
    return subjects


# ----------------------------------------------------------------------------- categories


def test_every_catalog_subject_maps_to_a_category_by_name() -> None:
    subjects = _seeded_subjects()
    assert len(subjects) > 150  # the whole 2026-27 catalog, not a sample
    unmapped = sorted(s for s in subjects if s not in fcat.SUBJECT_CATEGORY)
    assert unmapped == []


def test_categories_are_well_formed() -> None:
    keys = [c.key for c in fcat.CATEGORIES]
    assert 12 <= len(keys) <= 16 and len(set(keys)) == len(keys)
    assert fcat.FALLBACK in keys
    assert set(fcat.SUBJECT_CATEGORY.values()) <= set(keys)
    assert {c.motif for c in fcat.CATEGORIES} | set(fcat.SUBJECT_MOTIF.values()) <= MOTIFS
    for c in fcat.CATEGORIES:
        assert c.label and c.blurb and len(c.blurb) <= 100
        assert any(v == c.key for v in fcat.SUBJECT_CATEGORY.values()), c.key


def test_an_unknown_subject_falls_into_interdisciplinary() -> None:
    assert fcat.category_for("ZZZZ").key == "more"
    assert fcat.category_for("cmsc").key == "computing"
    assert fcat.motif_for("MUSI") == "notes"
    assert fcat.known_keys(["math", " Physical ", "nope", "math"]) == ["math", "physical"]


# ----------------------------------------------------------------------------- the shelf


def test_every_shelf_book_has_a_title_author_year_and_known_categories() -> None:
    books = shelf.load_shelf()
    assert 110 <= len(books) <= 160
    assert len({b.slug for b in books}) == len(books)
    assert len({b.title.casefold() for b in books}) == len(books)
    for b in books:
        assert b.title.strip() and b.author.strip()
        assert -800 <= b.year <= 2026, b.slug
        assert b.when
        assert set(b.categories) <= set(fcat.BY_KEY), b.slug
        assert b.keywords and all(k == k.lower() for k in b.keywords), b.slug
    covered = {c for b in books for c in b.categories}
    assert covered == set(fcat.BY_KEY)


def test_a_course_gets_at_most_two_books_that_really_overlap() -> None:
    found = shelf.books_for_course(
        "Introduction to Quantum Computing",
        "The key principles of quantum information science and quantum computing.",
        "computing",
    )
    assert [b.slug for b in found] == ["quantum-computation-and-quantum-information"]
    assert shelf.books_for_course("Elementary Basque I", "Grammar drills.", "languages") == []
    tragedy = shelf.books_for_course("Greek Tragedy", "Aeschylus and Sophocles.", "literature")
    assert 1 <= len(tragedy) <= 2


# ----------------------------------------------------------------------------- text


def test_excerpts_end_at_a_word() -> None:
    text = "word " * 100
    cut = ftext.excerpt(text, 300)
    assert len(cut) <= 300 and cut.endswith("…") and not cut.endswith(" …")
    assert ftext.excerpt("Short.", 300) == "Short."


def test_keywords_are_distinctive_and_keep_names() -> None:
    words = ftext.keywords(
        "Quantum Mechanics I",
        "A study of wave-particle duality and the Schrödinger equation. Students learn the "
        "postulates of quantum mechanics, the uncertainty principle and Hilbert spaces.",
        n=10,
    )
    assert 6 <= len(words) <= 10
    assert words[0] in ("quantum", "mechanics")
    assert "Schrödinger" in words and "Hilbert" in words
    assert not {"students", "learn", "the", "course"} & {w.lower() for w in words}


def test_topics_read_like_running_text() -> None:
    assert ftext.topic("Introduction to Quantum Computing", "quantum") == "quantum computing"
    assert ftext.topic("Gender and Sexuality in World Civilizations I") == "gender and sexuality"
    assert ftext.topic("Jewish Civilization I: Ancient Beginnings") == "Jewish civilization"


def test_markdown_becomes_scrubbed_plain_text() -> None:
    plain = ftext.plain_text("**Great** class, write me at jo@uchicago.edu or 773-702-1234")
    assert plain.startswith("Great class")
    assert "jo@" not in plain and "702" not in plain and "<" not in plain


def test_cloud_weights_run_from_one_to_five() -> None:
    words = ftext.cloud(["Quantum Mechanics I", "Quantum Field Theory", "Classical Mechanics"])
    weights = dict(words)
    assert weights["quantum"] == 5 and weights["mechanics"] == 5 and weights["theory"] == 1


# ----------------------------------------------------------------------------- the cursor


def test_a_cursor_round_trips_and_a_broken_one_starts_over() -> None:
    cursor = encode_cursor("explore", "2026-11-20", 24)
    assert decode_cursor(cursor, "explore") == ("2026-11-20", 24)
    assert decode_cursor(cursor, "for_you") == (None, 0)  # another tab's cursor
    for bad in ("", "!!!", "e30", encode_cursor("explore", "not-a-day", 3)):
        assert decode_cursor(bad, "explore") == (None, 0)


# ----------------------------------------------------------------------------- notes


def _described(id_: str, code: str | None = None) -> Described:
    return Described(
        id=id_,
        kind="course" if code else "book",
        label=f"{code} Something" if code else "A book",
        detail="Catalog text.",
        student_text=None,
        reason="Because you're into quantum computing",
        topic="quantum computing" if code else "a book",
        course_codes=(code,) if code else (),
    )


def test_notes_are_kept_only_for_asked_ids_and_known_courses() -> None:
    items = [_described("course:CMSC 19928", "CMSC 19928"), _described("book:cosmos")]
    answer = NotesAnswer.model_validate(
        {
            "headline": "Today's river: qubits and stars",
            "notes": [
                {"id": "course:CMSC 19928", "note": "Qubits, " + "very " * 60 + "much."},
                {
                    "id": "book:cosmos",
                    "note": "Pair it with MATH 99999, a course that is not here.",
                },
                {"id": "course:FAKE 10000", "note": "Not on the page."},
            ],
        }
    )
    headline, notes = checked(answer, items)
    assert headline == "Today's river: qubits and stars"
    assert set(notes) == {"course:CMSC 19928"}
    assert len(notes["course:CMSC 19928"]) <= NOTE_MAX


def test_a_headline_naming_an_unknown_course_is_dropped() -> None:
    items = [_described("course:CMSC 19928", "CMSC 19928")]
    answer = NotesAnswer(headline="Take PHYS 99999 today", notes=[])
    assert checked(answer, items) == (None, {})


def test_the_fallback_uses_the_feeds_own_reasons() -> None:
    items = [_described("course:CMSC 19928", "CMSC 19928")]
    out = fallback(items)
    assert out.ai is False
    assert out.notes == {"course:CMSC 19928": "Because you're into quantum computing"}
    assert out.headline == default_headline(items) == "Today's river: quantum computing"
    assert len(default_headline([_described(f"course:X {i}", f"ABCD 1000{i}") for i in range(5)]))


@pytest.mark.parametrize("n", [1, 2, 3])
def test_default_headlines_fit_ninety_characters(n: int) -> None:
    items = [
        Described(
            id=f"course:ABCD 1000{i}",
            kind="course",
            label="x",
            detail="",
            student_text=None,
            reason="r",
            topic="a rather long and winding topic name number " + str(i),
            course_codes=(f"ABCD 1000{i}",),
        )
        for i in range(n)
    ]
    assert len(default_headline(items)) <= 90
