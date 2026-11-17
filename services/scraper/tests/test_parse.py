"""Prompt 10: the selector engine and the deterministic parser, on SYNTHETIC fixtures only."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from scraper.dom import SelectorError, parse_html, validate_selector
from scraper.parse import (
    DEFAULT_CONFIG,
    ParseError,
    ParserConfig,
    parse_capacity,
    parse_meetings,
    parse_page,
    parse_status,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_every_fixture_is_labelled_synthetic() -> None:
    files = sorted(FIXTURES.glob("*.html"))
    assert files
    for f in files:
        assert f.name.startswith("SYNTHETIC_"), f.name
        assert "SYNTHETIC — not a real" in f.read_text(encoding="utf-8"), f.name
    assert "invented" in (FIXTURES / "README.md").read_text(encoding="utf-8")


def test_selectors() -> None:
    root = parse_html(
        '<div id="a" class="x y"><p class="x">one<br>two</p><ul><li data-k="1">i</li>'
        '<li data-k="2"><span class="x">ii</span></li></ul></div><p class="x">three</p>'
    )
    assert [n.text() for n in root.select("p.x")] == ["one two", "three"]
    assert [n.text() for n in root.select("#a .x")] == ["one two", "ii"]
    assert [n.text() for n in root.select("div > .x")] == ["one two"]
    assert [n.text() for n in root.select("li[data-k=2]")] == ["ii"]
    assert [n.text() for n in root.select("li[data-k='1'], span.x")] == ["i", "ii"]
    assert len(root.select("li[data-k]")) == 2
    assert root.select_one("table") is None
    # a scope never matches through its own ancestors
    ul = root.select_one("ul")
    assert ul is not None and ul.select("div li") == []
    for bad in ("", "p >", "> p", "p..x", "p > > q", ".x p#"):
        with pytest.raises(SelectorError):
            validate_selector(bad)
    with pytest.raises(ValueError, match="selector"):
        ParserConfig.model_validate({**DEFAULT_CONFIG.model_dump(), "section_row": "tr >"})


def test_text_lines_and_unclosed_tags() -> None:
    root = parse_html("<div><p>a <b>b</b><p>c</div></span><script>x()</script><td>d")
    assert root.text() == "a b c d"
    assert root.lines() == "a b\nc\nd"


def test_parses_the_synthetic_cmsc_page(html: Callable[[str], str]) -> None:
    sections = parse_page(html("SYNTHETIC_class_search_2026-AU_CMSC_p1.html"))
    assert [(s.course_code, s.section_no, s.component) for s in sections] == [
        ("CMSC 14100", "1", "LEC"),
        ("CMSC 14100", "2", "LEC"),
        ("CMSC 14100", "1A", "LAB"),
        ("CMSC 14200", "1", "LEC"),
    ]
    first, second, lab, two = sections
    assert first.instructors == ("Demo Instructor A",)
    assert first.meetings == (
        {
            "days": ["Mon", "Wed", "Fri"],
            "start": "10:30",
            "end": "11:20",
            "location": "Demo Hall 101",
        },
    )
    assert first.capacity == 80 and first.status == "open"
    assert second.meetings[0]["days"] == ["Tue", "Thu"] and second.meetings[0]["start"] == "09:30"
    assert second.status == "closed"
    assert lab.instructors == () and "location" not in lab.meetings[0]  # TBA dropped
    assert two.instructors == ("Demo Instructor A", "Demo Instrctor C")
    assert two.status == "waitlist" and two.subject == "CMSC"


def test_staff_tba_and_empty_pages(html: Callable[[str], str]) -> None:
    math = parse_page(html("SYNTHETIC_class_search_2026-AU_MATH_p1.html"))
    assert [s.instructors for s in math] == [("Demo Instructor E",), ("Instructor, Demo D",), ()]
    assert math[2].status == "cancelled"
    assert math[1].meetings[0]["start"] == "11:30" and math[1].meetings[0]["end"] == "12:20"
    fake = parse_page(html("SYNTHETIC_class_search_2026-AU_CMSC_p2.html"))
    assert fake[1].course_code == "CMSC 99901" and fake[1].meetings == ()
    assert parse_page(html("SYNTHETIC_class_search_2026-AU_empty.html")) == []


def test_changed_layout_fails_loudly(html: Callable[[str], str]) -> None:
    with pytest.raises(ParseError, match="no course blocks"):
        parse_page(html("SYNTHETIC_class_search_2026-AU_CMSC_p1_layout_v2.html"))
    with pytest.raises(ParseError, match="no results marker"):
        parse_page("<html><body>Please log in</body></html>")
    base = '<div id="class-search-results"><div class="course-block">{}</div></div>'
    with pytest.raises(ParseError, match="without a course code"):
        parse_page(base.format('<span class="course-code">Topics</span>'))
    with pytest.raises(ParseError, match="no section rows"):
        parse_page(base.format('<span class="course-code">CMSC 14100</span>'))
    row = '<span class="course-code">CMSC 14100</span><table>{}</table>'
    sec = '<tr class="section-row"><td class="section">1</td><td class="component">LEC</td></tr>'
    with pytest.raises(ParseError, match="duplicate"):
        parse_page(base.format(row.format(sec + sec)))
    with pytest.raises(ParseError, match="without a section number"):
        parse_page(
            base.format(row.format('<tr class="section-row"><td class="section"></td></tr>'))
        )


def test_cells() -> None:
    assert parse_meetings("TBA") == ()
    assert parse_meetings("") == ()
    assert parse_meetings("MW 12:00PM-1:20PM; F 12:00AM-12:50AM") == (
        {"days": ["Mon", "Wed"], "start": "12:00", "end": "13:20"},
        {"days": ["Fri"], "start": "00:00", "end": "00:50"},
    )
    assert parse_meetings("TuTh 3:30PM-4:50PM", "Demo Room")[0] == {
        "days": ["Tue", "Thu"],
        "start": "15:30",
        "end": "16:50",
        "location": "Demo Room",
    }
    for bad in ("Mondays 10:30AM-11:20AM", "MWF sometime", "MWF 13:30PM-14:20PM"):
        with pytest.raises(ParseError):
            parse_meetings(bad)
    assert parse_capacity("12/30") == 30 and parse_capacity("30") == 30
    assert parse_capacity(" ") is None
    with pytest.raises(ParseError):
        parse_capacity("lots")
    assert parse_status("Wait  List") == "waitlist" and parse_status("") is None
    with pytest.raises(ParseError):
        parse_status("Maybe")
