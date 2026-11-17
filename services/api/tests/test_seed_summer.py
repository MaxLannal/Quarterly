"""FEEDBACK "Check Summer Catalog" (Richard, 2026-11-16): Summer Session courses from
summer.uchicago.edu are documented in the seed, and a catalog course the Summer Session offers
is offered in Summer. No network here: records are written inline."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from api.seed.bundle import build_catalog, build_requisites, load_bundle
from api.seed.summer import build, parse, to_yaml
from planner_core import verify
from planner_core.models import PlanState, RuleSet

ROOT = Path(__file__).resolve().parents[3]
YEAR = ROOT / "data" / "seed" / "2026-27"


def record(**fields: Any) -> dict[str, Any]:
    base = {
        "courseSlug": "media-aesthetics-image-text-sound-i-11",
        "courseTitle": "Media Aesthetics: Image, Text, Sound I (11)",
        "courseType": "Undergraduate",
        "courseCode": "HUMA 16000 11",
        "startOfSession": "Session 4",
        "courseStartDate": "2026-08-03",
        "courseEndDate": "2026-08-21",
        "remoteOrCampus": "Residential",
        "coreCourse": True,
        "crossListedCourseCode": None,
    }
    return {**base, **fields}


def test_a_course_page_becomes_a_sourced_offering() -> None:
    o = parse(record(), {"HUMA 16000"})
    assert o is not None
    assert (o.code, o.section, o.session, o.core, o.in_catalog) == (
        "HUMA 16000",
        "11",
        "Session 4",
        True,
        True,
    )
    assert o.start == dt.date(2026, 8, 3) and o.end == dt.date(2026, 8, 21)
    assert o.source.quote == "HUMA 16000 11"
    assert (
        o.source.url
        == "https://summer.uchicago.edu/courses/media-aesthetics-image-text-sound-i-11/"
    )


def test_only_courses_for_college_students_with_a_code_are_kept() -> None:
    assert parse(record(courseType="Pre-College"), set()) is None
    assert parse(record(courseCode="TBA"), set()) is None
    both = parse(record(courseType="Both", crossListedCourseCode="ANTH 21420/SOSC 20224"), set())
    assert both is not None and both.crosslists == ["ANTH 21420", "SOSC 20224"]
    assert not both.in_catalog
    assert parse(record(courseCode="SOSC 20224"), {"SOSC 20224"}).section is None  # type: ignore[union-attr]


def test_the_yaml_reads_back() -> None:
    summer = build(
        [record(), record(courseType="Pre-College")], {"HUMA 16000"}, dt.date(2026, 11, 16)
    )
    assert summer.summer == 2026 and len(summer.summer_courses) == 1
    text = to_yaml(summer)
    assert "snapshot_id" not in text and "quote: HUMA 16000 11" in text


def test_the_seed_offers_summer_courses_in_summer() -> None:
    bundle = load_bundle(YEAR)
    assert len(bundle.summer) >= 100  # the 2026 finder lists 152 for College students
    catalog = build_catalog(bundle)
    summer = {o.course: o for o in catalog.offerings if o.quarter == "SU"}
    assert summer["HUMA 16000"].p_offered >= 0.9
    assert summer["HUMA 16000"].method == "summer_session"
    # Every pattern from the summer site belongs to a course that has a summer offering.
    offered = {c for s in bundle.summer for c in (s.code, *s.crosslists)}
    assert {o.course for o in summer.values() if o.method == "summer_session"} <= offered
    # A course placed in Summer that the Summer Session offers gets no "rarely offered" note.
    plan = PlanState.model_validate(
        {
            "catalog_year": "2026-27",
            "entry_term": "2026-AU",
            "items": [{"course": "HUMA 16000", "term": "2027-SU"}],
        }
    )
    rules = RuleSet(catalog_year="2026-27", requisites=build_requisites(bundle))
    report = verify(plan, rules, catalog)
    assert not [i for i in report.issues if "HUMA 16000" in i.course_ids and i.code == "V04"]
