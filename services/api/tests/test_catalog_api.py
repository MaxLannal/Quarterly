"""Catalog endpoints on the fake 2099-00 fixture, loaded into a throwaway database.

The bundle is extended in memory (never on disk): TEST 20200 gets core tag `arts`, a TEST 30000
whose prerequisite names the cross-listed FAKE 20100, `test-bs` is published, and a second
program `test-core` stays in review. A catalog year 2100-01 exists without courses."""

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from api.config import get_settings
from api.db import models as m
from api.db.session import get_session
from api.main import create_app
from api.seed.bundle import SeedBundle, integrity, load_bundle
from api.seed.loader import upsert_bundle
from api.seed.models import ProgramSeed, SeedCourse
from api_test_support import FIXTURES
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db

SRC = {"url": "https://example.invalid/fake-catalog", "quote": "FAKE FIXTURE - not a real course"}
SRC_OUT = {**SRC, "snapshot_id": None}
CORE_PROGRAM: dict[str, Any] = {
    "id": "test-core",
    "catalog_year": "2099-00",
    "name": "Test Core (fake)",
    "type": "core",
    "sources": [SRC],
    "rules": {
        "source": SRC,
        "group": {
            "all": True,
            "children": [
                {
                    "id": "arts",
                    "label": "Arts",
                    "source": SRC,
                    "select": {"count": 1, "from": {"tags": ["core:arts"]}},
                },
                {
                    "id": "mixed",
                    "source": SRC,
                    "select": {
                        "count": 2,
                        "from": {
                            "union": [{"list": "fake-seq-a"}, {"codes": ["FAKE 20100"]}],
                            "exclude": ["TEST 10100"],
                        },
                    },
                },
            ],
        },
    },
}


def fixture_bundle() -> SeedBundle:
    bundle = load_bundle(FIXTURES / "seed" / "2099-00")
    {c.code: c for c in bundle.courses}["TEST 20200"].core_tags = ["arts"]
    bundle.courses.append(
        SeedCourse.model_validate(
            {
                "code": "TEST 30000",
                "title": "Fake Capstone",
                "prereq": "FAKE 20100",
                "prereq_text": "FAKE 20100",
                "source": SRC,
            }
        )
    )
    test_bs = bundle.programs[0]
    test_bs.status, test_bs.verified_by = "published", "fake-curator"
    test_bs.verified_at = dt.date(2099, 9, 1)
    bundle.programs.append(ProgramSeed.model_validate(CORE_PROGRAM))
    assert integrity(bundle)[0] == []
    return bundle


def add_extras(session: Session) -> None:
    ids = {code: id_ for code, id_ in session.execute(sa.select(m.Course.code, m.Course.id))}
    session.add(m.CatalogYear(id="2100-01"))
    for key in ("workload_hours", "difficulty"):
        session.add(m.AttributeDef(key=key, scale="fake", description="fake"))
    session.flush()
    for subject_type, subject_id, key, value, method in [
        ("course", "TEST 10000", "workload_hours", 5.0, "forum"),
        ("course", "TEST 10000", "difficulty", 2.0, "forum"),
        ("course", "TEST 10100", "workload_hours", 12.0, "estimate"),
        ("course", "TEST 10100", "difficulty", 4.0, "estimate"),
        ("course", "TEST 20000", "difficulty", 3.5, "blend"),
        # Course x instructor values never count as course-level values.
        ("course_instructor", "TEST 20300", "workload_hours", 1.0, "forum"),
    ]:
        session.add(
            m.AttributeValue(
                subject_type=subject_type,
                subject_id=subject_id,
                key=key,
                value=value,
                n=4,
                method=method,
            )
        )
    session.add(
        m.Section(
            term_id="2099-AU",
            course_id=ids["TEST 10000"],
            section_no="1",
            component="LEC",
            instructor_ids=[7],
            meetings=[{"days": ["MO", "WE"], "start": "10:30", "end": "11:20"}],
        )
    )
    session.commit()


@pytest.fixture
def client(migrated_db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(get_settings(), "show_unpublished_programs", False)
    engine = sa.create_engine(migrated_db_url)
    with Session(engine) as session:
        upsert_bundle(session, fixture_bundle())
        add_extras(session)

    def session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def show_unpublished(monkeypatch: pytest.MonkeyPatch, value: bool = True) -> None:
    monkeypatch.setattr(get_settings(), "show_unpublished_programs", value)


def get(client: TestClient, path: str, status: int = 200, **params: Any) -> Any:
    resp = client.get(path, params=params)
    assert resp.status_code == status, resp.text
    return resp.json()


def codes(items: list[dict[str, Any]]) -> list[str]:
    return [item["code"] for item in items]


def search(client: TestClient, **params: Any) -> list[str]:
    return codes(get(client, "/courses", **params)["items"])


# ------------------------------------------------------------------------- years and terms


def test_catalog_years_terms_and_default_year(client: TestClient) -> None:
    assert [y["id"] for y in get(client, "/catalog-years")] == ["2100-01", "2099-00"]
    # 2100-01 has no courses, so 2099-00 stays the default.
    terms = ["2099-AU", "2100-WI", "2100-SP"]
    assert [t["id"] for t in get(client, "/terms")] == terms
    assert [t["id"] for t in get(client, "/terms", catalog_year="2099-00")] == terms
    assert get(client, "/terms", catalog_year="2100-01") == []
    assert get(client, "/courses", catalog_year="2100-01")["total"] == 0
    assert get(client, "/programs", catalog_year="2100-01") == []
    for path in ("/terms", "/courses", "/programs", "/courses/TEST%2010000"):
        detail = get(client, path, 404, catalog_year="1999-00")["detail"]
        assert detail == "Unknown catalog year 1999-00"


def test_empty_database_lists_nothing(migrated_db_url: str) -> None:
    engine = sa.create_engine(migrated_db_url)

    def session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = session_override
    client = TestClient(app)
    assert get(client, "/catalog-years") == []
    assert get(client, "/terms") == []
    assert get(client, "/courses") == {"items": [], "total": 0, "limit": 20, "offset": 0}
    assert get(client, "/programs") == []
    assert "No catalog data" in get(client, "/courses/TEST%2010000", 404)["detail"]
    engine.dispose()


# ----------------------------------------------------------------------------------- search


def test_search_by_code_in_any_spelling(client: TestClient) -> None:
    assert search(client, q="test 101") == ["TEST 10100"]
    assert search(client, q="TEST10000")[0] == "TEST 10000"
    assert search(client, q="test-20100")[0] == "TEST 20100"
    # Code prefix first; TEST 20100 has "fake" in its title and "201" in its code.
    assert search(client, q="fake 201") == ["FAKE 20100", "TEST 20100"]
    # Substring of the number: both cross-listed codes, by code.
    assert search(client, q="20100") == ["FAKE 20100", "TEST 20100"]


def test_search_ranks_code_hits_before_title_hits(client: TestClient) -> None:
    # "fake" is FAKE 20100's subject and starts every title.
    found = search(client, q="fake", limit=100)
    assert found[0] == "FAKE 20100"
    assert len(found) == 9
    assert search(client, q="Intro II") == ["TEST 10100"]
    assert search(client, q="intro") == ["TEST 10000", "TEST 10100"]
    assert search(client, q="exclusive b") == ["TEST 20300"]
    # Every word must match the code or the title.
    assert search(client, q="test capstone") == ["TEST 30000"]
    # Typos fall back to pg_trgm word similarity.
    assert search(client, q="Advancd") == ["TEST 20000"]
    assert search(client, q="Capstoen") == ["TEST 30000"]
    assert search(client, q="fake advancd") == ["TEST 20000"]
    # One fuzzy word does not let an unrelated word through.
    assert search(client, q="advancd zzzz") == []
    assert search(client, q="zzzz qqq") == []
    assert search(client, q="%") == []


def test_search_filters(client: TestClient) -> None:
    assert search(client, subject="fake") == ["FAKE 20100"]
    assert search(client, level=10000) == ["TEST 10000", "TEST 10100"]
    assert search(client, level=30000) == ["TEST 30000"]
    assert len(search(client, level=20000)) == 6
    assert get(client, "/courses", 422, level=15000)["detail"].startswith("level must be")
    assert search(client, quarter="AU") == ["TEST 10000"]
    assert search(client, quarter="WI") == ["TEST 10100"]
    assert search(client, quarter="SU") == []
    assert search(client, core_tag="arts") == ["TEST 20200"]
    assert search(client, core_tag="core:arts") == ["TEST 20200"]
    assert search(client, max_workload_hours=6) == ["TEST 10000"]
    assert search(client, max_workload_hours=12) == ["TEST 10000", "TEST 10100"]
    assert search(client, max_difficulty=3.5) == ["TEST 10000", "TEST 20000"]
    assert search(client, max_difficulty=4, max_workload_hours=20) == ["TEST 10000", "TEST 10100"]
    assert search(client, q="intro", quarter="WI") == ["TEST 10100"]
    assert search(client, subject="TEST", level=20000, q="exclusive") == [
        "TEST 20200",
        "TEST 20300",
    ]
    assert get(client, "/courses", 422, quarter="FA")["detail"][0]["loc"] == ["query", "quarter"]


def test_search_paging_and_summary_fields(client: TestClient) -> None:
    page = get(client, "/courses", limit=2, offset=0)
    assert (page["total"], page["limit"], page["offset"]) == (9, 2, 0)
    assert codes(page["items"]) == ["FAKE 20100", "TEST 10000"]
    assert codes(get(client, "/courses", limit=2, offset=8)["items"]) == ["TEST 30000"]
    items = {i["code"]: i for i in get(client, "/courses", limit=100)["items"]}
    assert items["TEST 20100"]["crosslists"] == ["FAKE 20100"]
    assert items["FAKE 20100"]["crosslists"] == ["TEST 20100"]
    assert items["TEST 10000"]["crosslists"] == []
    assert items["TEST 20200"]["core_tags"] == ["arts"]
    assert items["TEST 10000"]["title"] == "Fake Intro I" and items["TEST 10000"]["units"] == 100
    workload = {a["key"]: a for a in items["TEST 10100"]["attributes"]}
    assert workload["workload_hours"]["value"] == 12.0
    # A cold-start estimate is reported as a planner_core `prior`.
    assert workload["workload_hours"]["method"] == "prior"
    assert [a["key"] for a in items["TEST 10000"]["attributes"]] == ["difficulty", "workload_hours"]
    assert items["TEST 20300"]["attributes"] == []


# ------------------------------------------------------------------------------ course page


def test_course_detail(client: TestClient) -> None:
    course = get(client, "/courses/TEST%2010100")
    assert course["code"] == "TEST 10100" and course["catalog_year"] == "2099-00"
    assert course["prereq"] == {
        "op": "atom",
        "n": None,
        "children": [],
        "atom": {"kind": "course", "value": "TEST 10000", "min_grade": None},
    }
    assert course["prereq_text"] == "TEST 10000" and course["prereq_human"] == "TEST 10000"
    assert course["needs"] == ["TEST 10000"] and course["unlocks"] == ["TEST 20000"]
    assert [(o["quarter"], o["p_offered"]) for o in course["offerings"]] == [
        ("AU", 0.05),
        ("WI", 0.95),
        ("SP", 0.05),
    ]
    assert course["offerings"][0]["method"] == "catalog"
    assert course["source"] == SRC_OUT
    assert course["instructors"] == [] and course["sections"] == []
    assert course["coreq"] is None and course["restrictions"] is None

    advanced = get(client, "/courses/test-20000")
    assert advanced["prereq_human"] == "TEST 10100 and consent of instructor"
    assert advanced["prereq_text"] == "TEST 10100 and consent of instructor"
    assert advanced["needs"] == ["TEST 10100"] and advanced["unlocks"] == []
    assert advanced["offerings"] == []

    elective = get(client, "/courses/TEST20400")
    assert elective["needs"] == ["GONE 10000"]
    assert elective["prereq_human"] == "GONE 10000 (may be taken concurrently)"

    intro = get(client, "/courses/TEST%2010000")
    assert intro["prereq"] is None and intro["prereq_human"] is None and intro["needs"] == []
    assert intro["unlocks"] == ["TEST 10100"]
    assert intro["sections"] == [
        {
            "term": "2099-AU",
            "course": "TEST 10000",
            "section_no": "1",
            "component": "LEC",
            "instructor_ids": ["7"],
            "meetings": [{"days": ["MO", "WE"], "start": "10:30", "end": "11:20"}],
            "status": None,
        }
    ]
    assert {a["key"] for a in intro["attributes"]} == {"difficulty", "workload_hours"}


def test_course_relations_and_crosslists(client: TestClient) -> None:
    for code in ("TEST%2020200", "TEST-20300"):
        relations = get(client, f"/courses/{code}")["relations"]
        assert [(r["a"], r["b"], r["kind"]) for r in relations] == [
            ("TEST 20200", "TEST 20300", "mutually_exclusive")
        ]
    # TEST 30000 names FAKE 20100; its cross-listing TEST 20100 unlocks it too.
    for code in ("TEST%2020100", "FAKE%2020100"):
        course = get(client, f"/courses/{code}")
        assert course["unlocks"] == ["TEST 30000"]
    assert get(client, "/courses/TEST%2020100")["crosslists"] == ["FAKE 20100"]
    assert get(client, "/courses/TEST%2030000")["needs"] == ["FAKE 20100"]


def test_unknown_course_is_404(client: TestClient) -> None:
    assert get(client, "/courses/TEST%2099999", 404)["detail"] == (
        "Unknown course TEST 99999 in catalog year 2099-00"
    )
    assert "expected a code" in get(client, "/courses/nonsense", 404)["detail"]
    assert get(client, "/courses/GONE%2010000", 404)["detail"].startswith("Unknown course")


def test_counts_toward_follows_published_switch(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def toward(code: str) -> list[tuple[str, str, str | None]]:
        found = get(client, f"/courses/{code}")["counts_toward"]
        return [(c["program_id"], c["node_id"], c["label"]) for c in found]

    assert toward("TEST%2010000") == [
        ("test-bs", "test-bs/intro/1", None),
        ("test-bs", "test-bs/sequence/seq", None),
    ]
    assert toward("TEST%2020200") == [
        ("test-bs", "test-bs/electives", None),
        ("test-bs", "test-bs/sequence/seq", None),
    ]
    # Excluded from electives, in no list.
    assert toward("TEST%2020400") == []
    # Cross-listed with TEST 20100, which matches subject TEST.
    assert toward("FAKE%2020100") == [("test-bs", "test-bs/electives", None)]
    assert get(client, "/courses/TEST%2010000")["counts_toward"][0]["program_name"] == (
        "Test Studies BS (fake)"
    )

    show_unpublished(monkeypatch)
    assert toward("TEST%2020200") == [
        ("test-core", "test-core/arts", "Arts"),
        ("test-bs", "test-bs/electives", None),
        ("test-bs", "test-bs/sequence/seq", None),
    ]
    assert toward("FAKE%2020100") == [
        ("test-core", "test-core/mixed", None),
        ("test-bs", "test-bs/electives", None),
    ]
    assert ("test-core", "test-core/mixed", None) not in toward("TEST%2010100")


# ----------------------------------------------------------------------------- course lists


def test_course_lists(client: TestClient) -> None:
    seqs = get(client, "/course-lists/fake-seqs")
    assert seqs["courses"] == [] and seqs["sublists"] == ["fake-seq-a", "fake-seq-b"]
    assert seqs["source"] == SRC_OUT
    assert get(client, "/course-lists/fake-seq-b")["courses"] == ["TEST 20200", "TEST 20300"]
    assert get(client, "/course-lists/fake-seq-a", catalog_year="2099-00")["name"] == "fake-seq-a"
    assert get(client, "/course-lists/nope", 404)["detail"] == (
        "Unknown course list nope in catalog year 2099-00"
    )


# --------------------------------------------------------------------------------- programs


def test_programs_published_only_unless_setting(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    programs = get(client, "/programs")
    assert [(p["id"], p["status"]) for p in programs] == [("test-bs", "published")]
    assert programs[0] == {
        "id": "test-bs",
        "name": "Test Studies BS (fake)",
        "type": "major",
        "degree": "BS",
        "department": "Test Studies",
        "parent_id": None,
        "catalog_year": "2099-00",
        "status": "published",
        "verified_at": "2099-09-01",
    }
    assert get(client, "/programs", type="core") == []
    assert get(client, "/programs/test-core", 404)["detail"] == (
        "Program test-core has no published version for catalog year 2099-00"
    )
    assert get(client, "/programs/test-core/eligible", 404, node="test-core/arts")["detail"] == (
        "Program test-core has no published version for catalog year 2099-00"
    )

    show_unpublished(monkeypatch)
    programs = get(client, "/programs")
    assert [(p["id"], p["status"]) for p in programs] == [
        ("test-core", "review"),
        ("test-bs", "published"),
    ]
    assert [p["id"] for p in get(client, "/programs", type="core")] == ["test-core"]
    assert [p["id"] for p in get(client, "/programs", type="major")] == ["test-bs"]
    assert get(client, "/programs/test-core")["status"] == "review"
    assert get(client, "/programs", 422, type="nope")["detail"][0]["loc"] == ["query", "type"]

    show_unpublished(monkeypatch, False)
    assert [p["id"] for p in get(client, "/programs")] == ["test-bs"]


def test_program_detail(client: TestClient) -> None:
    program = get(client, "/programs/test-bs")
    assert program["id"] == "test-bs" and program["status"] == "published"
    assert isinstance(program["version_id"], int)
    assert program["checksum"].startswith("sha256:")
    assert program["verified_by"] == "fake-curator" and program["verified_at"] == "2099-09-01"
    assert program["sources"] == [SRC_OUT]
    share_src = {
        "url": "https://example.invalid/fake-catalog",
        "snapshot_id": None,
        "quote": "FAKE FIXTURE - not a real share limit",
    }
    assert program["policy"]["share"] == [
        {"with": "type:minor", "max": 0, "except": [], "source": share_src}
    ]
    rules = program["rules"]
    assert rules["kind"] == "group" and rules["all"] is True
    assert [c["id"] for c in rules["children"]] == ["intro", "electives", "sequence"]
    electives = rules["children"][1]
    assert electives["kind"] == "select" and electives["from"]["exclude"] == ["TEST 20400"]
    assert rules["children"][2]["parts"][0]["constraints"]["same_sequence"] is True
    assert program["sample_path"] == []
    assert get(client, "/programs/nope", 404)["detail"] == "Unknown program nope"


def test_eligible_courses(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def eligible(program: str, node: str, **params: Any) -> list[str]:
        return codes(get(client, f"/programs/{program}/eligible", node=node, **params))

    assert eligible("test-bs", "test-bs/intro/1") == ["TEST 10000"]
    assert eligible("test-bs", "test-bs/intro") == ["TEST 10000", "TEST 10100"]
    # Select: subject TEST, 20000-29999, minus TEST 20400; FAKE 20100 via its cross-listing.
    assert eligible("test-bs", "test-bs/electives") == [
        "FAKE 20100",
        "TEST 20000",
        "TEST 20100",
        "TEST 20200",
        "TEST 20300",
    ]
    assert eligible("test-bs", "electives") == eligible("test-bs", "test-bs/electives")
    assert eligible("test-bs", "test-bs/electives", limit=2) == ["FAKE 20100", "TEST 20000"]
    # Bounded part from a list of sublists, and the bounded_parts node itself.
    sequences = ["TEST 10000", "TEST 10100", "TEST 20200", "TEST 20300"]
    assert eligible("test-bs", "test-bs/sequence/seq") == sequences
    assert eligible("test-bs", "test-bs/sequence") == sequences
    # The root group: any course that fills some node.
    assert eligible("test-bs", "test-bs") == sorted(
        {*sequences, "FAKE 20100", "TEST 20000", "TEST 20100"}
    )
    summary = get(client, "/programs/test-bs/eligible", node="test-bs/electives")[2]
    assert summary["code"] == "TEST 20100" and summary["crosslists"] == ["FAKE 20100"]

    assert get(client, "/programs/test-bs/eligible", 404, node="test-bs/nope")["detail"] == (
        "Unknown node 'test-bs/nope' in program test-bs"
    )
    assert get(client, "/programs/nope/eligible", 404, node="x")["detail"] == "Unknown program nope"
    assert get(client, "/programs/test-bs/eligible", 422)["detail"][0]["loc"] == ["query", "node"]

    show_unpublished(monkeypatch)
    assert eligible("test-core", "test-core/arts") == ["TEST 20200"]
    # Union of a list and a code (with its cross-listing), minus an exclusion.
    assert eligible("test-core", "mixed") == ["FAKE 20100", "TEST 10000", "TEST 20100"]
