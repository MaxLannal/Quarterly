"""Prompt 10: the parser self-repair agent and the department-page extractor, with FakeLLM
only (no request reaches a model provider), plus the weekly watch end to end on a fake page."""

from __future__ import annotations

import contextlib
import datetime as dt
from collections.abc import Callable, Iterator
from typing import Any

import api.db.models as m
import pytest
import sqlalchemy as sa
from llm_gateway.api import FakeLLM, LLMUnavailableError, ToolCall
from scraper import review
from scraper.apply import NotAcceptedError, apply_department_plan_item
from scraper.dept_pages import (
    PlannedOffering,
    check_offering,
    extract_department_plan,
    page_text,
    planned_terms,
)
from scraper.parse import DEFAULT_CONFIG
from scraper.pipeline import active_config, run_schedule
from scraper.repair import propose_repair, verify_config
from scraper.settings import ScraperSettings
from scraper.snapshots import MemoryStore, record_snapshot
from scraper.watch import weekly_watch
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db
Snap = Callable[[str], int]

#: Selectors that read both the old and the changed SYNTHETIC layout.
BOTH = {
    **DEFAULT_CONFIG.model_dump(),
    "version": "synthetic-1-repair1",
    "course_block": "div.course-block, article.crs",
    "course_code": ".course-code, .crs-code",
    "section_row": "tr.section-row, li.sect",
    "section_no": "td.section, .sect-no",
    "component": "td.component, .sect-type",
    "instructors": "td.instructors, .sect-instr",
    "meetings": "td.meetings, .sect-time",
    "location": "td.location, .sect-room",
    "capacity": "td.capacity, .sect-seats",
    "status": "td.status, .sect-status",
}
#: Selectors that read only the changed layout (they lose the old pages).
NEW_ONLY = {
    **BOTH,
    "course_block": "article.crs",
    "course_code": ".crs-code",
    "section_row": "li.sect",
    "section_no": ".sect-no",
    "component": ".sect-type",
    "instructors": ".sect-instr",
    "meetings": ".sect-time",
    "location": ".sect-room",
    "capacity": ".sect-seats",
    "status": ".sect-status",
}
V2 = "SYNTHETIC_class_search_2026-AU_CMSC_p1_layout_v2.html"


def good_then_failed(db: Session, store: MemoryStore, snap: Snap) -> tuple[int, int, int]:
    good = run_schedule(
        db,
        store,
        "2026-AU",
        [
            snap("SYNTHETIC_class_search_2026-AU_CMSC_p1.html"),
            snap("SYNTHETIC_class_search_2026-AU_CMSC_p2.html"),
            snap("SYNTHETIC_class_search_2026-AU_MATH_p1.html"),
        ],
    )
    v2 = snap(V2)
    failed = run_schedule(db, store, "2026-AU", [v2])
    db.commit()
    assert good.status == "ok" and failed.status == "failed"
    return good.run_id, failed.run_id, v2


def test_verification_needs_the_old_counts(db: Session, store: MemoryStore, snap: Snap) -> None:
    good_id, _, v2 = good_then_failed(db, store, snap)
    good = db.get(m.ExtractionRun, good_id)
    assert good is not None and good.output is not None
    counts = {int(k): v for k, v in good.output["counts_by_snapshot"].items()}
    pages = {
        sid: store.get(row.storage_key)
        .decode()
        for sid in [*counts, v2]
        if (row := db.get(m.SourceSnapshot, sid)) is not None
    }  # fmt: skip
    from scraper.parse import ParserConfig

    ok = verify_config(pages, ParserConfig(**BOTH), good_counts=counts, failed_ids=[v2])
    assert ok.ok and ok.failed == {v2: 4}
    new_only = verify_config(pages, ParserConfig(**NEW_ONLY), good_counts=counts, failed_ids=[v2])
    assert not new_only.ok
    assert any("last good run" in p for p in new_only.problems)
    old = verify_config(pages, DEFAULT_CONFIG, good_counts=counts, failed_ids=[v2])
    assert not old.ok and any("still fails" in p for p in old.problems)


def test_repair_proposal_is_a_review_item(db: Session, store: MemoryStore, snap: Snap) -> None:
    good_id, failed_id, v2 = good_then_failed(db, store, snap)
    fake = FakeLLM(
        script={
            "scraper_repair": [
                ToolCall("read_snapshot", {"snapshot_id": v2, "offset": 0}),
                ToolCall("try_config", {"config": NEW_ONLY}),
                ToolCall("try_config", {"config": BOTH}),
                ToolCall(
                    "submit_parser_config",
                    {"config": BOTH, "explanation": "Course blocks became <article> elements."},
                ),
            ]
        }
    )
    item = propose_repair(db, store, fake, failed_id)
    db.commit()
    assert item.target_type == review.PARSER_REPAIR and item.target_id == f"run:{failed_id}"
    assert item.status == "open"
    assert item.diff["proposed_config"] == BOTH
    assert item.diff["old_config"] == DEFAULT_CONFIG.model_dump()
    assert item.diff["last_good_run_id"] == good_id and item.diff["verification"]["ok"]
    # the model saw the old parser and the page only as untrusted data
    first = fake.calls[0]
    assert first["task"] == "scraper_repair"
    assert "def parse_page" in str(first["messages"])
    tool_results = str(fake.calls[1]["messages"])
    assert "<untrusted_source" in tool_results and "&lt;article" in tool_results
    assert '"ok": false' in str(fake.calls[2]["messages"])  # NEW_ONLY loses the old pages
    assert set(first["tools"]) == {"read_snapshot", "try_config", "submit_parser_config"}

    # Nothing changes until a curator accepts it.
    assert active_config(db) == DEFAULT_CONFIG
    item.status = "accepted"
    db.commit()
    assert active_config(db).version == "synthetic-1-repair1"
    rerun = run_schedule(db, store, "2026-AU", [v2])
    assert rerun.status == "ok" and rerun.counts_by_subject == {"CMSC": 4}
    assert rerun.parser_version == "synthetic-1-repair1"


def test_bad_proposals_never_reach_the_parser(db: Session, store: MemoryStore, snap: Snap) -> None:
    _, failed_id, _ = good_then_failed(db, store, snap)
    bad = {"config": NEW_ONLY, "explanation": "only the new layout"}
    fake = FakeLLM(
        script={
            "scraper_repair": [
                ToolCall("submit_parser_config", bad),
                ToolCall("submit_parser_config", bad),  # the one repair turn, wasted
            ]
        }
    )
    item = propose_repair(db, store, fake, failed_id)
    db.commit()
    assert item.diff["proposed_config"] is None and "invalid_output" in item.diff["agent_error"]
    assert "developer" in (item.reason or "")
    assert "last good run" in str(fake.calls[1]["messages"])  # the check's message
    # No model configured at all: still a review item, so the failure is seen.
    again = propose_repair(db, store, FakeLLM(), failed_id)
    assert again.id == item.id and again.diff["proposed_config"] is None
    with pytest.raises(ValueError, match="not a failed"):
        propose_repair(db, store, fake, failed_id - 1)


# ------------------------------------------------------------------- department pages

ROW_141 = "CMSC 14100 Introduction to Computer Science I Autumn, Winter Demo Instructor A"
ROW_142 = "CMSC 14200 Introduction to Computer Science II Winter, Spring Demo Instructor B"


def test_offering_checks(html: Callable[[str], str]) -> None:
    text = page_text(html("SYNTHETIC_cs_course_info_2027-28.html"))
    assert ROW_141 in " ".join(text.split())

    def offer(**kw: Any) -> PlannedOffering:
        return PlannedOffering.model_validate(kw)

    assert check_offering(offer(course_code="CMSC 14100", quarters=["AU", "WI"],
                                instructor="Demo Instructor A", quote=ROW_141), text) is None  # fmt: skip
    assert "not on the page" in (
        check_offering(offer(course_code="CMSC 14300", quarters=["AU"],
                             quote="CMSC 14300 every Autumn"), text) or ""
    )  # fmt: skip
    assert "code is not in the quote" in (
        check_offering(offer(course_code="CMSC 14100", quarters=["WI"], quote=ROW_142), text) or ""
    )
    assert "does not name AU" in (
        check_offering(offer(course_code="CMSC 14200", quarters=["AU"], quote=ROW_142), text) or ""
    )
    assert "instructor" in (
        check_offering(offer(course_code="CMSC 14200", quarters=["WI"], instructor="Demo X",
                             quote=ROW_142), text) or ""
    )  # fmt: skip
    assert planned_terms("2027-28", "AU") == "2027-AU"
    assert planned_terms("2027-28", "WI") == "2028-WI"
    assert planned_terms("2027-28", "SU") == "2027-SU"


def test_department_plan_extraction(
    db: Session, store: MemoryStore, html: Callable[[str], str], snap: Snap
) -> None:
    # Autumn 2026 posted: CMSC 14100 AU is p = 1 for 2026-AU; the 2027-28 plan still applies.
    run_schedule(db, store, "2026-AU", [snap("SYNTHETIC_class_search_2026-AU_CMSC_p1.html")])
    page = record_snapshot(
        db,
        store,
        url="synthetic://cs-course-info",
        body=html("SYNTHETIC_cs_course_info_2027-28.html").encode(),
        fetched_at=dt.datetime(2026, 11, 3, tzinfo=dt.UTC),
        prefix="dept-pages",
    )
    db.commit()
    answer = {
        "offerings": [
            {"course_code": "CMSC 14100", "quarters": ["AU", "WI"],
             "instructor": "Demo Instructor A", "quote": ROW_141},
            {"course_code": "CMSC 14200", "quarters": ["WI", "SP", "AU"], "quote": ROW_142},
            {"course_code": "CMSC 11111", "quarters": ["SP"],
             "quote": "CMSC 11111\nCreative Coding\nSpring"},
            {"course_code": "CMSC 99902", "quarters": ["AU"],
             "quote": "CMSC 99902 Invented Seminar (FAKE code) Autumn"},
            {"course_code": "CMSC 14300", "quarters": ["AU"], "quote": "CMSC 14300 every Autumn"},
        ]
    }  # fmt: skip
    fake = FakeLLM(script={"dept_offerings_extraction": [answer]})
    item = extract_department_plan(
        db, store, fake, page.id, department="CMSC", academic_year="2027-28"
    )
    db.commit()
    prompt = str(fake.calls[0]["messages"])
    assert "<untrusted_source" in prompt and "Demo Instructor A" in prompt
    assert item.target_type == review.DEPT_PLAN and item.target_id == "CMSC:2027-28"
    assert [o["course_code"] for o in item.diff["accepted"]] == ["CMSC 14100", "CMSC 11111"]
    assert item.diff["accepted"][0]["terms"] == ["2027-AU", "2028-WI"]
    assert [o["course_code"] for o in item.diff["unknown_codes"]] == ["CMSC 99902"]
    reasons = {o["course_code"]: o["rejected_because"] for o in item.diff["rejected"]}
    assert reasons == {
        "CMSC 14200": "the quote does not name AU",
        "CMSC 14300": "the quote is not on the page",
    }
    run = db.get(m.ExtractionRun, item.diff["run_id"])
    assert run is not None and run.model == "dept_offerings_extraction" and run.status == "ok"
    assert run.input_snapshot_ids == [page.id]

    def pattern(code: str, quarter: str) -> m.OfferingPattern | None:
        return db.scalar(
            sa.select(m.OfferingPattern)
            .join(m.Course, m.Course.id == m.OfferingPattern.course_id)
            .where(m.Course.code == code, m.OfferingPattern.quarter == quarter)
        )

    with pytest.raises(NotAcceptedError):
        apply_department_plan_item(db, item.id)
    assert pattern("CMSC 11111", "SP") is None  # nothing applied yet
    item.status = "accepted"
    db.commit()
    assert apply_department_plan_item(db, item.id) == 3
    db.commit()
    for code, quarter in (("CMSC 14100", "AU"), ("CMSC 14100", "WI"), ("CMSC 11111", "SP")):
        row = pattern(code, quarter)
        assert row is not None and row.p_offered == 0.95 and row.method == "department_plan"
    au = pattern("CMSC 14100", "AU")
    assert au is not None and au.evidence_terms == ["2027-AU"]


def test_department_plan_without_a_model(
    db: Session, store: MemoryStore, html: Callable[[str], str]
) -> None:
    page = record_snapshot(
        db,
        store,
        url="synthetic://cs-course-info",
        body=html("SYNTHETIC_cs_course_info_2027-28.html").encode(),
        fetched_at=dt.datetime(2026, 11, 3, tzinfo=dt.UTC),
    )
    with pytest.raises(LLMUnavailableError):
        extract_department_plan(db, store, FakeLLM(), page.id, department="CMSC",
                                academic_year="2027-28")  # fmt: skip
    run = db.scalar(sa.select(m.ExtractionRun).where(m.ExtractionRun.kind == "dept_offerings"))
    assert run is not None and run.status == "failed"
    assert db.scalar(sa.select(sa.func.count()).select_from(m.ReviewItem)) == 0


# ------------------------------------------------------------------------ weekly watch


def test_weekly_watch(
    db: Session, store: MemoryStore, fake_site: Any, html: Callable[[str], str]
) -> None:
    opened: list[str] = []

    @contextlib.contextmanager
    def factory(settings: ScraperSettings) -> Iterator[Any]:
        opened.append("page")
        yield fake_site

    off = ScraperSettings(_env_file=None)  # type: ignore[call-arg]
    assert weekly_watch(db, store, off, FakeLLM(), today=dt.date(2026, 7, 1),
                        page_factory=factory) == ["disabled: SCHEDULE_SCRAPER_ENABLED is not true"]  # fmt: skip
    assert opened == []  # no browser, no request

    on = ScraperSettings(  # type: ignore[call-arg]
        _env_file=None,
        schedule_scraper_enabled=True,
        class_search_url="synthetic://class-search",
        scraper_delay_s=0,
    )
    lines = weekly_watch(db, store, on, FakeLLM(), today=dt.date(2026, 7, 1), page_factory=factory)
    assert lines[0].startswith("2026-AU: 3 pages, run ") and "ok, 8 sections" in lines[0]
    assert lines[1] == "2027-WI: not posted yet"
    assert db.scalar(sa.select(sa.func.count()).select_from(m.SourceSnapshot)) == 3
    assert db.scalar(sa.select(sa.func.count()).select_from(m.Section)) == 8

    # The layout changes: the run fails and a repair review item is opened.
    fake_site.pages[("Autumn 2026", "CMSC", 1)] = html(V2)
    lines = weekly_watch(db, store, on, FakeLLM(), today=dt.date(2026, 7, 1), page_factory=factory)
    assert "failed, repair review item" in lines[0]
    (repair,) = db.scalars(
        sa.select(m.ReviewItem).where(m.ReviewItem.target_type == review.PARSER_REPAIR)
    ).all()
    assert repair.diff["proposed_config"] is None
