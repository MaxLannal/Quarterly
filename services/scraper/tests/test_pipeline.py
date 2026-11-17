"""Prompt 10: pipeline runs on stored SYNTHETIC snapshots: sections, checks, review items,
forum pages (cross-listing aware), offering patterns, and what a curator's decision applies."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import api.db.models as m
import pytest
import sqlalchemy as sa
from scraper import review
from scraper.apply import NotAcceptedError, apply_instructor_match
from scraper.pipeline import NOT_LISTED, run_schedule
from scraper.snapshots import MemoryStore, read_snapshot, record_snapshot
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db
Snap = Callable[[str], int]


def items(db: Session, kind: str) -> list[m.ReviewItem]:
    return list(
        db.scalars(
            sa.select(m.ReviewItem)
            .where(m.ReviewItem.target_type == kind)
            .order_by(m.ReviewItem.id)
        )
    )


def course_id(db: Session, code: str) -> int:
    cid = db.scalar(sa.select(m.Course.id).where(m.Course.code == code))
    assert cid is not None
    return cid


def instructor(db: Session, name: str) -> m.Instructor:
    row = db.scalar(sa.select(m.Instructor).where(m.Instructor.display_name == name))
    assert row is not None
    return row


def last_year(db: Session, store: MemoryStore, snap: Snap) -> None:
    report = run_schedule(
        db, store, "2025-AU", [snap("SYNTHETIC_class_search_2025-AU_CMSC_p1.html")]
    )
    db.commit()
    assert report.status == "ok" and report.counts_by_subject == {"CMSC": 2}


def this_year(db: Session, store: MemoryStore, snap: Snap) -> Any:
    ids = [
        snap("SYNTHETIC_class_search_2026-AU_CMSC_p1.html"),
        snap("SYNTHETIC_class_search_2026-AU_CMSC_p2.html"),
        snap("SYNTHETIC_class_search_2026-AU_MATH_p1.html"),
        snap("SYNTHETIC_class_search_2026-AU_empty.html"),
    ]
    report = run_schedule(db, store, "2026-AU", ids)
    db.commit()
    return report


def test_snapshots_are_stored_once_and_checked(db: Session, store: MemoryStore, snap: Snap) -> None:
    a = snap("SYNTHETIC_class_search_2026-AU_CMSC_p1.html")
    assert snap("SYNTHETIC_class_search_2026-AU_CMSC_p1.html") == a  # same URL, same bytes
    row, text = read_snapshot(db, store, a)
    assert row.storage_key.startswith("class-search/") and "CMSC 14100" in text
    store.objects[row.storage_key] = b"tampered"
    with pytest.raises(ValueError, match="sha256"):
        read_snapshot(db, store, a)


def test_full_run(db: Session, store: MemoryStore, snap: Snap) -> None:
    # An existing page under the cross-listed code: the run must reuse it (ensure_page).
    madd = m.CourseInstructor(
        course_id=course_id(db, "MADD 21111"),
        instructor_id=instructor(db, "Demo Instructor B").id,
        first_term="2026-AU",
        last_term="2026-AU",
        n_terms=1,
    )
    db.add(madd)
    db.commit()
    last_year(db, store, snap)
    report = this_year(db, store, snap)

    assert report.status == "ok"
    assert report.counts_by_subject == {"CMSC": 5, "MATH": 3}  # CMSC 99901 is not saved
    assert sum(report.counts_by_snapshot.values()) == 9
    assert report.sections_written == 8 and report.sections_unlisted == 0

    run = db.get(m.ExtractionRun, report.run_id)
    assert run is not None and run.kind == "schedule_parse" and run.status == "ok"
    assert run.input_snapshot_ids == report.snapshot_ids and run.model == "deterministic"
    assert run.output is not None and run.output["counts_by_subject"] == {"CMSC": 5, "MATH": 3}

    # sections
    rows = db.scalars(
        sa.select(m.Section).where(m.Section.term_id == "2026-AU").order_by(m.Section.id)
    ).all()
    assert len(rows) == 8
    first = rows[0]
    a = instructor(db, "Demo Instructor A")
    assert first.instructor_ids == [a.id] and first.capacity == 80 and first.status == "open"
    assert first.meetings[0]["days"] == ["Mon", "Wed", "Fri"]
    assert first.source_id == report.snapshot_ids[0] and first.scraped_at is not None

    # unknown code -> review, not saved
    (unknown,) = items(db, review.UNKNOWN_CODE)
    assert unknown.target_id == "2026-AU:CMSC 99901" and unknown.status == "open"
    assert unknown.diff["kind"] == review.UNKNOWN_CODE and unknown.diff["run_id"] == run.id
    assert unknown.diff["snapshot_ids"] == [report.snapshot_ids[1]]

    # names: exact and "Last, First" match; the typo goes to review; nobody is merged
    (typo,) = items(db, review.INSTRUCTOR_MATCH)
    assert typo.diff["name"] == "Demo Instrctor C"
    assert {c["display_name"] for c in typo.diff["candidates"]} >= {"Demo Instructor A"}
    assert typo.diff["sections"] == [{"course": "CMSC 14200", "section": "1", "component": "LEC"}]
    cmsc142 = db.scalar(
        sa.select(m.Section).where(m.Section.course_id == course_id(db, "CMSC 14200"),
                                   m.Section.term_id == "2026-AU")
    )  # fmt: skip
    assert cmsc142 is not None and cmsc142.instructor_ids == [a.id]
    d = instructor(db, "Demo Instructor D")
    math20 = db.scalar(sa.select(m.Section).where(m.Section.section_no == "20"))
    assert math20 is not None and math20.instructor_ids == [d.id]
    assert report.new_instructors == []  # E, D, A, B all existed

    # count alert: CMSC 5 vs 2 last year (+150%); MATH has no baseline
    (alert,) = items(db, review.COUNT_ALERT)
    assert alert.target_id == "2026-AU:CMSC"
    assert alert.diff["count"] == 5 and alert.diff["baseline"] == 2 and alert.diff["change"] == 1.5
    assert sorted(report.review_item_ids) == sorted([unknown.id, typo.id, alert.id])

    # forum pages: one per course x instructor; CMSC 11111 reuses the MADD 21111 page
    pages = db.execute(
        sa.select(m.Course.code, m.Instructor.display_name, m.CourseInstructor)
        .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
        .join(m.Instructor, m.Instructor.id == m.CourseInstructor.instructor_id)
        .order_by(m.Course.code, m.Instructor.display_name)
    ).all()
    assert [(c, n) for c, n, _ in pages] == [
        ("CMSC 14100", "Demo Instructor A"),
        ("CMSC 14100", "Demo Instructor B"),
        ("CMSC 14200", "Demo Instructor A"),
        ("MADD 21111", "Demo Instructor B"),  # the cross-listed page, reused
        ("MATH 15100", "Demo Instructor D"),
        ("MATH 15100", "Demo Instructor E"),
    ]
    cs141_a = pages[0][2]
    assert (cs141_a.first_term, cs141_a.last_term, cs141_a.n_terms) == ("2025-AU", "2026-AU", 2)
    assert report.pages_created == 3  # D, E on MATH and B on CMSC 14100 (A's were last year)

    # offering patterns: listed now -> p = 1 with the evidence terms
    pattern = db.scalar(
        sa.select(m.OfferingPattern).where(
            m.OfferingPattern.course_id == course_id(db, "CMSC 14100"),
            m.OfferingPattern.quarter == "AU",
        )
    )
    assert pattern is not None and pattern.p_offered == 1.0 and pattern.method == "posted_schedule"
    assert pattern.evidence_terms == ["2025-AU", "2026-AU"]


def test_rerun_updates_in_place(db: Session, store: MemoryStore, snap: Snap) -> None:
    this_year(db, store, snap)
    n_items = db.scalar(sa.select(sa.func.count()).select_from(m.ReviewItem))
    # The next week, MATH page 1 lists the same sections; CMSC page 2 is gone.
    report = run_schedule(
        db,
        store,
        "2026-AU",
        [snap("SYNTHETIC_class_search_2026-AU_CMSC_p1.html"),
         snap("SYNTHETIC_class_search_2026-AU_MATH_p1.html")],
    )  # fmt: skip
    db.commit()
    assert report.status == "ok"
    assert db.scalar(sa.select(sa.func.count()).select_from(m.Section)) == 8  # no duplicates
    gone = db.scalar(sa.select(m.Section).where(m.Section.course_id == course_id(db, "CMSC 11111")))
    assert gone is not None and gone.status == NOT_LISTED and report.sections_unlisted == 1
    # open items are refreshed, not duplicated (the unknown code was not seen this time)
    assert db.scalar(sa.select(sa.func.count()).select_from(m.ReviewItem)) == n_items
    pattern = db.scalar(
        sa.select(m.OfferingPattern).where(
            m.OfferingPattern.course_id == course_id(db, "CMSC 11111")
        )
    )
    assert pattern is not None and pattern.method == "history" and pattern.p_offered == 0.2


def test_history_formula_in_the_database(db: Session, store: MemoryStore, snap: Snap) -> None:
    """CMSC 14200 in AU 2024 and 2025, not in the 2026 schedule: k = 2 -> p = 0.6."""
    cid = course_id(db, "CMSC 14200")
    for term in ("2024-AU", "2025-AU"):
        db.add(m.Term(id=term, year=int(term[:4]), quarter="AU"))
        db.flush()
        db.add(m.Section(term_id=term, course_id=cid, section_no="1", component="LEC"))
    db.commit()
    ids = [snap("SYNTHETIC_class_search_2026-AU_MATH_p1.html")]
    # a CMSC page without CMSC 14200: only CMSC 11111 (page 2) is listed for CMSC
    ids.append(snap("SYNTHETIC_class_search_2026-AU_CMSC_p2.html"))
    run_schedule(db, store, "2026-AU", ids)
    db.commit()
    row = db.scalar(sa.select(m.OfferingPattern).where(m.OfferingPattern.course_id == cid))
    assert row is not None and row.method == "history"
    assert row.p_offered == pytest.approx(0.6) and row.evidence_terms == ["2024-AU", "2025-AU"]


def test_failed_run_writes_nothing(db: Session, store: MemoryStore, snap: Snap) -> None:
    report = run_schedule(
        db, store, "2026-AU", [snap("SYNTHETIC_class_search_2026-AU_CMSC_p1_layout_v2.html")]
    )
    db.commit()
    assert report.status == "failed" and "no course blocks" in report.errors[0]["error"]
    assert db.scalar(sa.select(sa.func.count()).select_from(m.Section)) == 0
    run = db.get(m.ExtractionRun, report.run_id)
    assert run is not None and run.status == "failed"
    zero = run_schedule(db, store, "2026-AU", [snap("SYNTHETIC_class_search_2026-AU_empty.html")])
    assert zero.status == "failed" and "zero sections" in zero.errors[0]["error"]
    missing = run_schedule(db, store, "2026-AU", [999999])
    assert missing.status == "failed" and "LookupError" in missing.errors[0]["error"]


def test_new_instructor_is_created(db: Session, store: MemoryStore) -> None:
    page = (
        '<div id="class-search-results"><div class="course-block">'
        '<span class="course-code">MATH 15100</span><table><tr class="section-row">'
        '<td class="section">40</td><td class="component">LEC</td>'
        '<td class="instructors">Zelda Quixote-Fake</td></tr></table></div></div>'
    )
    sid = record_snapshot(
        db, store, url="synthetic://inline", body=page.encode(), fetched_at=dt_now()
    ).id
    report = run_schedule(db, store, "2026-AU", [sid])
    db.commit()
    assert report.new_instructors == ["Zelda Quixote-Fake"]
    person = instructor(db, "Zelda Quixote-Fake")
    assert person.slug == "zelda-quixote-fake" and person.department == "MATH"
    assert report.pages_created == 1


def dt_now() -> Any:
    import datetime as dt

    return dt.datetime(2026, 11, 2, tzinfo=dt.UTC)


def test_instructor_match_applies_only_after_acceptance(
    db: Session, store: MemoryStore, snap: Snap
) -> None:
    this_year(db, store, snap)
    (item,) = items(db, review.INSTRUCTOR_MATCH)
    with pytest.raises(NotAcceptedError):
        apply_instructor_match(db, item.id, None)
    item.status = "accepted"
    db.commit()
    new_id = apply_instructor_match(db, item.id, None)  # "a new person"
    db.commit()
    section = db.scalar(
        sa.select(m.Section).where(m.Section.course_id == course_id(db, "CMSC 14200"))
    )
    assert section is not None and new_id in section.instructor_ids
    page = db.scalar(
        sa.select(m.CourseInstructor).where(m.CourseInstructor.instructor_id == new_id)
    )
    assert page is not None and page.first_term == "2026-AU"
    # choosing an existing person records the spelling as an alias
    other = m.ReviewItem(
        target_type=review.INSTRUCTOR_MATCH,
        target_id="x",
        diff={"name": "Demo Instrctor A", "term_id": "2026-AU", "sections": []},
        status="accepted",
    )
    db.add(other)
    db.commit()
    a = instructor(db, "Demo Instructor A")
    assert apply_instructor_match(db, other.id, a.id) == a.id
    assert a.aliases == ["Demo Instrctor A"]


def test_worker_job_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from scraper.settings import get_scraper_settings
    from worker.main import WorkerSettings, weekly_schedule_watch

    monkeypatch.delenv("SCHEDULE_SCRAPER_ENABLED", raising=False)
    get_scraper_settings.cache_clear()
    try:
        assert asyncio.run(weekly_schedule_watch({})).startswith("disabled")
    finally:
        get_scraper_settings.cache_clear()
    assert weekly_schedule_watch in WorkerSettings.functions
    assert any(j.coroutine is weekly_schedule_watch for j in WorkerSettings.cron_jobs)
