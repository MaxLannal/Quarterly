import copy
from pathlib import Path

import pytest
import sqlalchemy as sa
from api.cli import main as cli_main
from api.db import models as m
from api.seed.bundle import SeedError, build_catalog, build_rules, discover, integrity, load_bundle
from api.seed.loader import upsert_bundle
from api_test_support import FIXTURES
from planner_core.models import ProgramRules, Source
from sqlalchemy.orm import Session

YEAR_DIR = FIXTURES / "seed" / "2099-00"


def test_fixture_bundle_validates_and_builds() -> None:
    assert [p.name for p in discover(FIXTURES / "seed")] == ["2099-00"]
    bundle = load_bundle(YEAR_DIR)
    errors, warnings = integrity(bundle)
    assert errors == []
    assert warnings == ["course TEST 20400: prereq names GONE 10000, not in the seed"]
    catalog = build_catalog(bundle)
    assert catalog.crosslist_groups == [["FAKE 20100", "TEST 20100"]]
    assert [(r.a, r.b, r.kind) for r in catalog.relations] == [
        ("TEST 20200", "TEST 20300", "mutually_exclusive")
    ]
    offered = {(o.course, o.quarter): o.p_offered for o in catalog.offerings}
    assert offered[("TEST 10000", "AU")] == 0.95 and offered[("TEST 10000", "WI")] == 0.05
    rules = build_rules(bundle)
    assert [p.id for p in rules.programs] == ["test-bs"]
    assert rules.college is not None and rules.college.total_units == 800
    assert {r.course for r in rules.requisites} == {"TEST 10100", "TEST 20000", "TEST 20400"}
    assert build_rules(bundle, []).programs == []


def test_integrity_catches_unknown_refs_and_missing_sources() -> None:
    bundle = load_bundle(YEAR_DIR)
    broken = copy.deepcopy(bundle)
    broken.courses = [c for c in broken.courses if c.code != "TEST 10100"]
    broken.programs[0].rules.children[0].children[0].source = None  # type: ignore[union-attr]
    broken.course_lists[0].source = None
    broken.course_lists[1].sublists = ["nope"]
    errors, _ = integrity(broken)
    joined = "\n".join(errors)
    assert "test-bs/intro/2: unknown course TEST 10100" in joined
    assert "test-bs/intro/1: missing source" in joined
    assert "course list fake-seqs: missing source" in joined
    assert "course list fake-seq-a: unknown course TEST 10100" in joined
    assert "unknown sublist nope" in joined


def test_bad_yaml_is_reported_with_file(tmp_path: Path) -> None:
    year = tmp_path / "2099-00"
    year.mkdir()
    (year / "courses.yaml").write_text("courses: [{code: TEST 10000}]")
    with pytest.raises(SeedError, match=r"courses\.yaml"):
        load_bundle(year)
    (year / "courses.yaml").write_text("courses: [")
    with pytest.raises(SeedError, match="invalid YAML"):
        load_bundle(year)


def test_cli_seed_dry_run_and_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["seed", "--dir", str(FIXTURES / "seed"), "--dry-run"]) == 0
    assert "valid (8 courses, 1 programs)" in capsys.readouterr().out
    assert cli_main(["seed", "--dir", str(tmp_path)]) == 0
    assert "no catalog years" in capsys.readouterr().out


@pytest.mark.db
def test_loader_upserts_idempotently(
    migrated_db_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        cli_main(["seed", "--dir", str(FIXTURES / "seed"), "--database-url", migrated_db_url]) == 0
    )
    assert "courses=8" in capsys.readouterr().out
    engine = sa.create_engine(migrated_db_url)
    with Session(engine) as session:
        counts = upsert_bundle(session, load_bundle(YEAR_DIR))
        assert counts["programs"] == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(m.Course)) == 8
        assert session.scalar(sa.select(sa.func.count()).select_from(m.CrosslistGroup)) == 2
        assert session.scalar(sa.select(sa.func.count()).select_from(m.CourseRelation)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(m.Requisite)) == 3
        assert session.scalar(sa.select(sa.func.count()).select_from(m.ProgramVersion)) == 1
        version = session.scalars(sa.select(m.ProgramVersion)).one()
        program = ProgramRules.model_validate(version.rules)
        assert program.id == "test-bs" and version.status == "review"
        assert version.checksum.startswith("sha256:")
        assert Source.model_validate(version.sources[0]).quote.startswith("FAKE")
        lists = {cl.name: cl for cl in session.scalars(sa.select(m.CourseList))}
        assert lists["fake-seqs"].sublists == ["fake-seq-a", "fake-seq-b"]
        assert len(lists["fake-seq-a"].course_ids) == 2
    engine.dispose()
