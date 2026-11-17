"""POST /verify against a throwaway database seeded with the fake fixture (catalog year
2099-00) and an in-memory Redis."""

import logging
from collections.abc import Iterator
from typing import Any

import fakeredis
import pytest
import redis
import sqlalchemy as sa
from api.config import Settings
from api.db import models as m
from api.db.session import get_session
from api.main import app
from api.repo.rules import UnknownProgramsError, load_verify_inputs
from api.routers import verify as verify_router
from api.seed.bundle import build_catalog, build_rules, load_bundle
from api.seed.loader import upsert_bundle
from api_test_support import FIXTURES
from fastapi.testclient import TestClient
from planner_core import CORE_VERSION, check_certificate, verify
from planner_core.models import Certificate, PlanState, Report
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.db
YEAR_DIR = FIXTURES / "seed" / "2099-00"
GOOD = {
    "catalog_year": "2099-00",
    "entry_term": "2099-AU",
    "programs": [{"program_id": "test-bs"}],
    "items": [
        {"course": "TEST 10000", "term": "2099-AU"},
        {"course": "TEST 10100", "term": "2100-WI"},
        {"course": "TEST 20000", "term": "2100-SP"},
        {"course": "FAKE 20100", "term": "2100-SP"},  # cross-listed with TEST 20100
    ],
}
CHECKS = {"checks": ["V01", "V02", "V03", "V07"]}


class Env:
    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine
        self.cache = fakeredis.FakeRedis()
        self.client = TestClient(app)
        self.settings = Settings(show_unpublished_programs=True)

    def post(self, plan: dict[str, Any], options: dict[str, Any] | None = None) -> Any:
        return self.client.post(
            "/verify", json={"plan": plan, "options": CHECKS if options is None else options}
        )

    def session(self) -> Session:
        return Session(self.engine)


@pytest.fixture
def env(migrated_db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    engine = sa.create_engine(migrated_db_url)
    with Session(engine) as session:
        upsert_bundle(session, load_bundle(YEAR_DIR))
    made = Env(engine)

    def sessions() -> Iterator[Session]:
        with sessionmaker(engine)() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[verify_router.get_cache] = lambda: made.cache
    monkeypatch.setattr(verify_router, "get_settings", lambda: made.settings)
    try:
        yield made
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_verify_returns_a_checked_report_and_caches_it(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    resp = env.post(GOOD)
    assert resp.status_code == 200, resp.text
    report = Report.model_validate(resp.json())
    assert report.status == "warnings"  # TEST 20000 needs the instructor's consent
    assert [(i.code, i.level) for i in report.issues] == [("V03", "warning")]
    assert report.core_version == CORE_VERSION and report.certificate is not None
    used = {a.node: a.courses for a in report.certificate.assignments}
    assert used["test-bs/electives"] == ["FAKE 20100", "TEST 20000"]
    assert used["test-bs/sequence/seq"] == ["TEST 10000", "TEST 10100"]  # double counting allowed
    assert any(p.node_id == "test-bs" and p.satisfied for p in report.progress)

    # the certificate checks against the same inputs the seed files give
    bundle = load_bundle(YEAR_DIR)
    plan = PlanState.model_validate(GOOD)
    assert check_certificate(
        plan, build_rules(bundle, ["test-bs"]), build_catalog(bundle), report.certificate
    )

    # cached under verify:{core_version}:{digest}:{plan_hash}, with a TTL
    (key,) = env.cache.keys("verify:*")
    prefix, version, digest, hashed = key.decode().split(":", 3)
    assert (prefix, version) == ("verify", CORE_VERSION)
    assert digest == "sha256" and hashed.endswith(report.plan_hash)
    assert 0 < env.cache.ttl(key) <= verify_router.CACHE_TTL_S

    # the second call is served from the cache
    def boom(*args: object) -> None:
        raise AssertionError("verify ran although the report was cached")

    monkeypatch.setattr(verify_router, "verify_checked", boom)
    assert env.post(GOOD).json() == resp.json()
    # item order and ids do not change the plan hash
    shuffled = {
        **GOOD,
        "items": [{**i, "id": str(n)} for n, i in enumerate(reversed(GOOD["items"]))],
    }
    assert env.post(shuffled).json() == resp.json()


def test_verify_reports_errors_with_all_checks(env: Env) -> None:
    bad = {
        **GOOD,
        "items": [
            {"course": "TEST 10000", "term": "2099-AU"},
            {"course": "TEST 10100", "term": "2099-AU"},
        ],
    }
    resp = env.post(bad, {})
    assert resp.status_code == 200
    report = Report.model_validate(resp.json())
    assert report.status == "errors" and report.certificate is None
    codes = {i.code for i in report.issues if i.level == "error"}
    assert {"V03", "V07", "V09"} <= codes  # the fixture policy wants 800 units and the Core
    v03 = next(i for i in report.issues if i.code == "V03")
    assert v03.course_ids == ["TEST 10100"] and v03.fix_hints
    assert any(
        p.node_id == "college/total_units" and (p.have, p.need) == (200, 800)
        for p in report.progress
    )
    # different options -> a different cache entry
    assert env.post(bad).status_code == 200
    assert len(env.cache.keys("verify:*")) == 2


def test_unknown_and_unpublished_programs_are_422(env: Env) -> None:
    resp = env.post({**GOOD, "programs": [{"program_id": "test-bs"}, {"program_id": "nope-ba"}]})
    assert resp.status_code == 422
    (detail,) = resp.json()["detail"]
    assert detail["loc"] == ["body", "plan", "programs", 1, "program_id"]
    assert detail["msg"] == "Unknown program for catalog year 2099-00: nope-ba"
    assert env.post({**GOOD, "catalog_year": "2098-99"}).status_code == 422

    # the fixture version has status `review`: hidden unless show_unpublished_programs is on
    env.settings = Settings(show_unpublished_programs=False)
    assert env.post(GOOD).status_code == 422
    with env.session() as session:
        session.execute(sa.update(m.ProgramVersion).values(status="published"))
        session.commit()
    assert env.post(GOOD).status_code == 200

    # a plan bound to a program_version id
    with env.session() as session:
        version_id = session.scalar(sa.select(m.ProgramVersion.id))
    bound = {**GOOD, "programs": [{"program_id": "test-bs", "version_id": version_id}]}
    assert env.post(bound).status_code == 200
    elsewhere = {**GOOD, "programs": [{"program_id": "test-bs", "version_id": version_id + 1}]}
    assert env.post(elsewhere).status_code == 422
    # malformed bodies are still plain validation errors
    assert env.post({"catalog_year": "2099-00", "entry_term": "2099-FA"}).status_code == 422
    # no programs, unknown catalog year: every course is unknown, but it is still a report
    report = env.post({**GOOD, "programs": [], "catalog_year": "2098-99"}).json()
    assert report["status"] == "errors" and {i["code"] for i in report["issues"]} == {"V01"}


def test_reseeding_invalidates_the_cache(env: Env) -> None:
    first = env.post(GOOD).json()
    assert first["status"] == "warnings"
    with env.session() as session:  # the catalog changes: TEST 20000 loses its requisite
        course_id = session.scalar(sa.select(m.Course.id).where(m.Course.code == "TEST 20000"))
        session.execute(sa.delete(m.Requisite).where(m.Requisite.course_id == course_id))
        session.commit()
    second = env.post(GOOD).json()
    assert second["status"] == "valid" and second["plan_hash"] == first["plan_hash"]
    assert len(env.cache.keys("verify:*")) == 2


class DownRedis:
    def get(self, key: str) -> None:
        raise redis.ConnectionError("down")

    def set(self, *args: object, **kwargs: object) -> None:
        raise redis.ConnectionError("down")


def test_redis_down_still_answers(env: Env, caplog: pytest.LogCaptureFixture) -> None:
    app.dependency_overrides[verify_router.get_cache] = DownRedis
    with caplog.at_level(logging.WARNING, logger="api.verify"):
        resp = env.post(GOOD)
    assert resp.status_code == 200 and resp.json()["status"] == "warnings"
    assert "cache read failed" in caplog.text and "cache write failed" in caplog.text
    # a corrupt cache entry is ignored too
    app.dependency_overrides[verify_router.get_cache] = lambda: env.cache
    env.post(GOOD)
    (key,) = env.cache.keys("verify:*")
    env.cache.set(key, b"not json")
    assert env.post(GOOD).status_code == 200


def test_a_rejected_certificate_is_dropped_alerted_and_not_cached(
    env: Env, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import sys

    # make the checker disagree with the solver
    monkeypatch.setattr(
        sys.modules["planner_core.verify"],
        "certificate_problems",
        lambda *a: ["test-bs is not satisfied"],
    )
    with caplog.at_level(logging.ERROR, logger="api.verify"):
        resp = env.post(GOOD)
    assert resp.status_code == 200
    report = resp.json()
    assert report["status"] == "errors" and report["certificate"] is None
    assert "Internal check failed" in report["issues"][-1]["message"]
    assert "ALERT certificate rejected" in caplog.text and report["plan_hash"] in caplog.text
    assert env.cache.keys("verify:*") == []


def test_partial_checks_are_never_valid_when_a_hidden_check_fails(env: Env) -> None:
    # all of the certificate's own checks hold: a restricted run is certified
    report = env.post(GOOD, {"checks": ["V01", "V02"]}).json()
    assert report["status"] == "valid" and report["certificate"] is not None
    hidden = env.post(GOOD, {**CHECKS, "include_certificate": False}).json()
    assert hidden["status"] == "warnings" and hidden["certificate"] is None
    # the program is incomplete, but V07 was not asked for: never "valid"
    short = {**GOOD, "items": GOOD["items"][:2]}
    report = env.post(short, {"checks": ["V01", "V02"]}).json()
    assert report["status"] == "warnings" and report["certificate"] is None
    assert "Partial check" in report["issues"][-1]["message"]


def test_loader_matches_the_seed_files_and_loads_only_what_the_plan_needs(env: Env) -> None:
    plan = PlanState.model_validate(
        {**GOOD, "credits": [{"kind": "AP", "label": "AP", "maps_to": "TEST 20200", "units": 100}]}
    )
    with env.session() as session:
        rules, catalog = load_verify_inputs(session, plan, show_unpublished=True)
        with pytest.raises(UnknownProgramsError, match="test-bs"):
            load_verify_inputs(session, plan)
    bundle = load_bundle(YEAR_DIR)
    assert rules.programs == build_rules(bundle, ["test-bs"]).programs
    assert rules.college == bundle.college
    assert {c.code for c in catalog.courses} == {
        "TEST 10000",
        "TEST 10100",
        "TEST 20000",
        "TEST 20100",  # cross-listed partner of FAKE 20100
        "FAKE 20100",
        "TEST 20200",  # the credit
    }
    assert catalog.crosslist_groups == [["FAKE 20100", "TEST 20100"]]
    assert [(r.a, r.b, r.kind) for r in catalog.relations] == [
        ("TEST 20200", "TEST 20300", "mutually_exclusive")
    ]
    assert {r.course for r in rules.requisites} == {"TEST 10100", "TEST 20000"}
    assert {cl.name: cl.courses for cl in catalog.course_lists}["fake-seq-b"] == [
        "TEST 20200",
        "TEST 20300",
    ]
    assert {(o.course, o.quarter, o.p_offered) for o in catalog.offerings} >= {
        ("TEST 10000", "AU", 0.95)
    }
    # the subset gives the same report as the whole seed
    full = verify(plan, build_rules(bundle, ["test-bs"]), build_catalog(bundle))
    assert verify(plan, rules, catalog) == full


def test_sections_attributes_and_the_posted_term_marker(env: Env) -> None:
    with env.session() as session:
        ids = dict(session.execute(sa.select(m.Course.code, m.Course.id)).all())
        session.add_all(
            [
                m.Section(
                    term_id="2099-AU",
                    course_id=ids["TEST 10000"],
                    section_no="1",
                    component="LEC",
                    instructor_ids=[7],
                    meetings=[{"days": ["MO"], "start": "09:30", "end": "10:50"}, {"days": "bad"}],
                ),
                # 2100-SP is posted, but none of the plan's courses is offered in it
                m.Section(
                    term_id="2100-SP", course_id=ids["TEST 20400"], section_no="1", meetings=[]
                ),
                m.AttributeDef(key="workload_hours", scale="hours/week", description="fake"),
                m.AttributeDef(key="mystery", scale="?", description="not a planner_core key"),
            ]
        )
        session.flush()
        session.add_all(
            [
                m.AttributeValue(
                    subject_type="course",
                    subject_id="TEST 10000",
                    key="workload_hours",
                    value=9.5,
                    method="estimate",
                ),
                m.AttributeValue(
                    subject_type="course",
                    subject_id="TEST 10000",
                    key="mystery",
                    value=1,
                    method="prior",
                ),
            ]
        )
        session.commit()
        _, catalog = load_verify_inputs(
            session, PlanState.model_validate(GOOD), show_unpublished=True
        )
    assert [(s.term, s.course, len(s.meetings)) for s in catalog.sections] == [
        ("2099-AU", "TEST 10000", 1),
        ("2100-SP", "TEST 20400", 0),
    ]
    assert catalog.sections[0].instructor_ids == ["7"]
    assert [(a.subject_id, a.key, a.value, a.method) for a in catalog.attributes] == [
        ("TEST 10000", "workload_hours", 9.5, "prior")
    ]
    # the posted schedule wins: the Spring courses are not on it
    report = Report.model_validate(env.post(GOOD, {"checks": ["V04"]}).json())
    assert sorted(i.course_ids[0] for i in report.issues if i.level == "error") == [
        "FAKE 20100",
        "TEST 20000",
    ]
    goal = {"id": "g1", "type": "workload_hours", "max_hours": 9, "hard": True}
    report = Report.model_validate(env.post({**GOOD, "goals": [goal]}, {"checks": ["V11"]}).json())
    assert [(i.code, i.level, i.goal_id) for i in report.issues] == [("V11", "error", "g1")]


def test_certificate_schema_round_trips_through_the_api(env: Env) -> None:
    raw = env.post(GOOD).json()["certificate"]
    assert set(raw) == {"plan_hash", "rules", "assignments", "prereq_witnesses", "loads", "goals"}
    assert list(raw["rules"]) == ["test-bs@2099-00"]
    assert Certificate.model_validate(raw).prereq_witnesses[0].by == ["TEST 10000@2099-AU"]
