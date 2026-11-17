"""The curator review queue (prompt 09): `/admin/review-items`, decisions, publishing.

Admins only, with the session's CSRF token on every decision; nothing reaches students until
an admin publishes a version."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from api.db import models as m
from auth_test_support import migrated_database
from forum_test_support import YEAR, ForumEnv, forum_env
from planner_core.hashing import sha256_of
from planner_core.models import ProgramRules
from sqlalchemy import select

pytestmark = pytest.mark.db

SRC = {"url": "https://example.test/fake-catalog/", "quote": "FAKE: take TEST 10100."}
RULES = {
    "id": "fake-major",
    "catalog_year": YEAR,
    "type": "major",
    "rules": {
        "id": "fake-major",
        "group": {
            "all": True,
            "children": [{"id": "intro", "slot": {"any_of": ["TEST 10100"]}, "source": SRC}],
        },
        "source": SRC,
    },
}


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def f(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[ForumEnv]:
    with forum_env(db_url, monkeypatch) as env:
        yield env


def add_version(
    f: ForumEnv, *, item: bool = True, status: str = "review"
) -> tuple[int, int | None]:
    rules = ProgramRules.model_validate(RULES)
    with f.env.db() as db:
        db.add(m.Program(id="fake-major", name="Fake Major", type="major"))
        db.flush()
        version = m.ProgramVersion(
            program_id="fake-major",
            catalog_year=YEAR,
            rules=rules.model_dump(mode="json"),
            status=status,
            checksum=sha256_of(rules),
        )
        db.add(version)
        db.flush()
        item_id = None
        if item:
            row = m.ReviewItem(
                target_type="program_version",
                target_id=str(version.id),
                diff={
                    "kind": "program_version",
                    "program_id": "fake-major",
                    "catalog_year": YEAR,
                    "program_version_id": version.id,
                    "decision_hint": "review",
                    "rules": rules.model_dump(mode="json"),
                    "nodes": [
                        {
                            "path": "fake-major/intro",
                            "kind": "slot",
                            "summary": "TEST 10100",
                            "quote": SRC["quote"],
                            "url": SRC["url"],
                            "flags": ["The second run disagrees here (different)."],
                        }
                    ],
                    "checks": [
                        {"id": "c", "name": "Quotes are verbatim", "ok": True, "problems": []}
                    ],
                },
                reason="fake-major: new program; all checks passed",
            )
            db.add(row)
            db.flush()
            item_id = row.id
        db.commit()
        return version.id, item_id


def add_item(f: ForumEnv, target_type: str, target_id: str, diff: dict[str, Any]) -> int:
    with f.env.db() as db:
        row = m.ReviewItem(target_type=target_type, target_id=target_id, diff=diff, reason="test")
        db.add(row)
        db.commit()
        return row.id


def test_only_admins_see_or_decide(f: ForumEnv) -> None:
    _, item_id = add_version(f)
    student = f.user()
    assert student.get("/admin/review-items").status_code == 403
    assert (
        student.post(f"/admin/review-items/{item_id}/decision", {"decision": "accept"}).status_code
        == 403
    )
    anonymous = f.env.browser()
    assert anonymous.get("/admin/review-items").status_code == 401


def test_decisions_need_the_csrf_token(f: ForumEnv) -> None:
    _, item_id = add_version(f)
    admin = f.admin()
    resp = admin.client.post(f"/admin/review-items/{item_id}/decision", json={"decision": "accept"})
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


def test_list_shows_nodes_with_quotes_and_checks(f: ForumEnv) -> None:
    version_id, item_id = add_version(f)
    admin = f.admin()
    resp = admin.get("/admin/review-items")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "private, no-store"
    page = resp.json()
    assert page["total"] == 1
    item = page["items"][0]
    assert item["id"] == item_id
    assert item["title"] == f"fake-major {YEAR}"
    assert item["program_version_id"] == version_id
    assert item["program_version_status"] == "review"
    assert item["nodes"][0]["quote"] == SRC["quote"]
    assert item["nodes"][0]["flags"]
    assert item["checks"][0]["id"] == "c"
    assert admin.get("/admin/review-items?status=accepted").json()["total"] == 0


def test_accept_then_publish_reaches_students(f: ForumEnv) -> None:
    version_id, item_id = add_version(f)
    admin = f.admin()
    # Not yet: the review item is still open.
    blocked = admin.post(f"/admin/program-versions/{version_id}/publish")
    assert blocked.status_code == 409
    decided = admin.post(
        f"/admin/review-items/{item_id}/decision", {"decision": "accept", "note": "ok"}
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "accepted"
    assert decided.json()["decided_at"] is not None
    again = admin.post(f"/admin/review-items/{item_id}/decision", {"decision": "reject"})
    assert again.status_code == 409
    published = admin.post(f"/admin/program-versions/{version_id}/publish")
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["status"] == "published"
    assert body["verified_by"] == "curator"  # never an admin username (public on program pages)
    assert admin.post(f"/admin/program-versions/{version_id}/publish").status_code == 409
    with f.env.db() as db:
        row = db.scalar(select(m.ReviewItem).where(m.ReviewItem.id == item_id))
        assert row is not None and row.decided_by is not None
        assert row.diff["curator_note"] == "ok"


def test_reject_sends_the_version_back_to_draft(f: ForumEnv) -> None:
    version_id, item_id = add_version(f)
    admin = f.admin()
    resp = admin.post(f"/admin/review-items/{item_id}/decision", {"decision": "reject"})
    assert resp.status_code == 200
    assert resp.json()["program_version_status"] == "draft"
    assert admin.post(f"/admin/program-versions/{version_id}/publish").status_code == 409


def test_edit_replaces_the_rules_and_is_validated(f: ForumEnv) -> None:
    version_id, item_id = add_version(f)
    admin = f.admin()
    unsourced = {
        **RULES["rules"],
        "group": {"all": True, "children": [{"id": "x", "slot": {"any_of": ["TEST 20100"]}}]},
    }
    bad = admin.post(
        f"/admin/review-items/{item_id}/decision",
        {"decision": "edit", "edited": {"rules": {"rules": unsourced}}},
    )
    assert bad.status_code == 422
    assert "source" in bad.json()["detail"]
    edited_rules = {
        "rules": {
            "id": "fake-major",
            "group": {
                "all": True,
                "children": [
                    {"id": "intro", "slot": {"any_of": ["TEST 10100", "TEST 20100"]}, "source": SRC}
                ],
            },
            "source": SRC,
        }
    }
    ok = admin.post(
        f"/admin/review-items/{item_id}/decision",
        {"decision": "edit", "edited": {"rules": edited_rules}},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "accepted"
    assert ok.json()["nodes"][1]["summary"] == "Edited by a curator"
    with f.env.db() as db:
        version = db.get(m.ProgramVersion, version_id)
        assert version is not None
        assert version.rules["rules"]["children"][0]["any_of"] == ["TEST 10100", "TEST 20100"]
        assert version.status == "review"
    assert admin.post(f"/admin/program-versions/{version_id}/publish").status_code == 200


def test_a_version_without_review_items_can_be_published(f: ForumEnv) -> None:
    version_id, _ = add_version(f, item=False)
    admin = f.admin()
    assert admin.post(f"/admin/program-versions/{version_id}/publish").status_code == 200
    assert admin.post("/admin/program-versions/999999/publish").status_code == 404


def test_requisite_items_write_the_prerequisite(f: ForumEnv) -> None:
    admin = f.admin()
    diff = {
        "kind": "requisite",
        "catalog_year": YEAR,
        "course": "TEST 20100",
        "raw_text": "TEST 10100 or consent of instructor.",
        "proposed": None,
        "errors": ["names TEST 99999, which is not in the catalog"],
        "source": {"snapshot_id": None, "quote": "TEST 10100 or consent of instructor."},
    }
    item_id = add_item(f, "requisite", f"{YEAR}:TEST 20100", diff)
    nothing = admin.post(f"/admin/review-items/{item_id}/decision", {"decision": "accept"})
    assert nothing.status_code == 409
    expr = {"any": ["TEST 10100", {"consent": "instructor"}]}
    ok = admin.post(
        f"/admin/review-items/{item_id}/decision", {"decision": "edit", "edited": {"prereq": expr}}
    )
    assert ok.status_code == 200, ok.text
    with f.env.db() as db:
        req = db.scalar(select(m.Requisite).where(m.Requisite.catalog_year == YEAR))
        assert req is not None and req.prereq is not None
        assert req.prereq["op"] == "any"
        assert req.raw_text == "TEST 10100 or consent of instructor."


def test_course_batch_accept_writes_the_courses(f: ForumEnv) -> None:
    admin = f.admin()
    src = {
        "snapshot_id": "not-a-row",
        "url": "https://example.test/fake/",
        "quote": "FAKE 10100. A. 100 Units.",
    }
    course = {
        "code": "FAKE 10100", "subject": "FAKE", "number": "10100", "title": "A", "units": 100,
        "description": "FAKE course.", "notes": None, "prereq_text": None,
        "terms_offered": ["AU"], "crosslists": ["FAKE 20100"], "source": src,
    }  # fmt: skip
    other = {
        **course,
        "code": "FAKE 20100",
        "number": "20100",
        "title": "B",
        "crosslists": ["FAKE 10100"],
    }
    diff = {
        "kind": "course_batch",
        "catalog_year": "2100-01",
        "subject": "FAKE",
        "courses": [course, other],
        "crosslist_groups": [["FAKE 10100", "FAKE 20100"]],
        "relations": [{"a": "FAKE 20100", "b": "FAKE 10100", "kind": "replaces", "source": src}],
        "requisites": {
            "FAKE 20100": {
                "prereq": {"op": "atom", "atom": {"kind": "course", "value": "FAKE 10100"}},
                "raw_text": "FAKE 10100",
            }
        },
    }
    item_id = add_item(f, "course_batch", "2100-01:FAKE", diff)
    edit = admin.post(f"/admin/review-items/{item_id}/decision", {"decision": "edit", "edited": {}})
    assert edit.status_code == 422
    ok = admin.post(f"/admin/review-items/{item_id}/decision", {"decision": "accept"})
    assert ok.status_code == 200, ok.text
    with f.env.db() as db:
        codes = set(db.scalars(select(m.Course.code).where(m.Course.catalog_year == "2100-01")))
        assert codes == {"FAKE 10100", "FAKE 20100"}
        assert len(db.scalars(select(m.CrosslistGroup)).all()) == 2
        assert db.scalar(select(m.CourseRelation.kind)) == "replaces"
        assert (
            db.scalar(select(m.Requisite.raw_text).where(m.Requisite.catalog_year == "2100-01"))
            == "FAKE 10100"
        )
        offered = db.scalars(select(m.OfferingPattern.quarter)).all()
        assert sorted(offered) == ["AU", "AU", "SP", "SP", "WI", "WI"]  # both courses


def test_other_item_types_only_record_the_decision(f: ForumEnv) -> None:
    admin = f.admin()
    item_id = add_item(
        f, "catalog_change", "2099-00:2099-08-15", {"kind": "catalog_change", "changed": []}
    )
    resp = admin.post(
        f"/admin/review-items/{item_id}/decision", {"decision": "edit", "edited": {"note": "seen"}}
    )
    assert resp.status_code == 200
    assert resp.json()["diff"]["edited_content"] == {"note": "seen"}
    assert (
        admin.post("/admin/review-items/999999/decision", {"decision": "accept"}).status_code == 404
    )
