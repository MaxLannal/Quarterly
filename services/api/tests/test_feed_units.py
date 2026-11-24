"""The browse rows' pieces without a database (issue #19): categories cover the catalog, the
text helpers, and the hand-written list of new courses is well formed and quotes its sources."""

from __future__ import annotations

from pathlib import Path

import yaml
from api.feed import categories as fcat
from api.feed import new_courses
from api.feed import text as ftext

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


# ----------------------------------------------------------------------------- text


def test_excerpts_end_at_a_word() -> None:
    text = "word " * 100
    cut = ftext.excerpt(text, 300)
    assert len(cut) <= 300 and cut.endswith("…") and not cut.endswith(" …")
    assert ftext.excerpt("Short.", 300) == "Short."


def test_markdown_becomes_scrubbed_plain_text() -> None:
    plain = ftext.plain_text("**Great** class, write me at jo@uchicago.edu or 773-702-1234")
    assert plain.startswith("Great class")
    assert "jo@" not in plain and "702" not in plain and "<" not in plain


# ----------------------------------------------------------------------------- new courses


def test_the_new_courses_list_is_valid_and_quotes_every_source() -> None:
    path = ROOT / "data" / "catalog" / "new_courses.yaml"
    listed = new_courses.NewCoursesFile.model_validate(yaml.safe_load(path.read_text()))
    assert listed.catalog_year == "2026-27"
    seeded = {
        str(c["code"])
        for p in sorted(SEED.glob("*.yaml"))
        for c in yaml.safe_load(p.read_text())["courses"]
    }
    for entry in listed.courses:
        assert entry.code in seeded, entry.code
        assert entry.source.quote.strip() and entry.source.url.startswith("https://")
