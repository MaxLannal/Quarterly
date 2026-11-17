"""The annual run and the monthly check against a real (throwaway) database, the FAKE catalog
server and FakeLLM. Nothing is ever published by the pipeline."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from api.db import models as m
from auth_test_support import migrated_database
from ingest_rules import RULES, URL, rules_yaml
from llm_gateway.api import FakeLLM, ToolCall
from sqlalchemy.orm import sessionmaker
from test_ingest_pipeline import E1_ANSWERS, candidates, script
from worker.ingest.jobs import annual_run, monthly_check
from worker.ingest.settings import IngestSettings
from worker.ingest.snapshots import MemoryStore

pytestmark = pytest.mark.db


@pytest.fixture
def factory() -> Iterator[Any]:
    with migrated_database() as url:
        engine = sa.create_engine(url)
        try:
            yield sessionmaker(engine)
        finally:
            engine.dispose()


def settings(server: Any) -> IngestSettings:
    return IngestSettings(
        _env_file=None,  # type: ignore[call-arg]
        catalog_ingest_enabled=True,
        catalog_base_url=server.base_url,
        catalog_counts_url=f"{server.base_url}/programs-study/",
        catalog_contact_email="bot@example.edu",
        catalog_target_year="2099-00",
    )


def test_annual_run_writes_review_items_and_review_versions(
    factory: Any, catalog_server: Any, clock: Any
) -> None:
    base = catalog_server.base_url
    tree = json.loads(json.dumps(RULES).replace(URL, f"{base}/thecollege/fakescience/"))
    fake = FakeLLM(
        script={
            "e1_prereq_formalizer": list(E1_ANSWERS),
            "e2_program_enumerator": [
                ToolCall("submit_programs", {"candidates": candidates(base)})
            ],
        }
    )
    script(fake, rules_yaml(tree))
    store = MemoryStore()
    kw = {"clock": clock.time, "sleep": clock.sleep, "require_https": False}
    counts = annual_run(
        settings(catalog_server), factory, fake, agents=True, store=store, crawler_kw=kw
    )
    assert counts["program_versions"] == 1
    with factory() as db:
        snaps = db.scalars(sa.select(m.SourceSnapshot)).all()
        assert len(snaps) == len(catalog_server.requests)
        assert all(s.storage_key in store.objects for s in snaps)
        version = db.scalar(sa.select(m.ProgramVersion))
        assert (
            version is not None and version.status == "review" and version.program_id == "fsci-bs"
        )
        assert version.source_ids and all(isinstance(i, int) for i in version.source_ids)
        # Quotes point at real snapshot rows (read_snapshot ids are the row ids).
        assert (
            db.scalar(
                sa.select(sa.func.count())
                .select_from(m.ProgramVersion)
                .where(m.ProgramVersion.status == "published")
            )
            == 0
        )
        items = db.scalars(sa.select(m.ReviewItem)).all()
        by_type: dict[str, int] = {}
        for item in items:
            by_type[item.target_type] = by_type.get(item.target_type, 0) + 1
            assert item.status == "open"
        assert by_type["course_batch"] == 2 and by_type["program_version"] == 1
        assert by_type["requisite"] == 1
        pv_item = next(i for i in items if i.target_type == "program_version")
        assert pv_item.target_id == str(version.id)
        assert pv_item.diff["program_version_id"] == version.id
        assert (
            db.scalar(sa.select(sa.func.count()).select_from(m.Course)) == 0
        )  # staged, not applied
        runs = {r.kind for r in db.scalars(sa.select(m.ExtractionRun))}
        assert {"e1", "e2", "e3", "e3b", "e4"} <= runs


def test_a_published_version_is_never_overwritten(
    factory: Any, catalog_server: Any, clock: Any
) -> None:
    from planner_core.models import ProgramRules

    with factory() as db:
        db.add(m.CatalogYear(id="2099-00"))
        db.add(m.Program(id="fsci-bs", name="Fake Science (BS)", type="major"))
        db.flush()
        db.add(
            m.ProgramVersion(
                program_id="fsci-bs",
                catalog_year="2099-00",
                rules=ProgramRules.model_validate(RULES).model_dump(mode="json"),
                status="published",
                checksum="sha256:x",
            )
        )
        db.commit()
    base = catalog_server.base_url
    tree = json.loads(json.dumps(RULES).replace(URL, f"{base}/thecollege/fakescience/"))
    fake = FakeLLM(
        script={
            "e1_prereq_formalizer": list(E1_ANSWERS),
            "e2_program_enumerator": [
                ToolCall("submit_programs", {"candidates": candidates(base)})
            ],
        }
    )
    script(fake, rules_yaml(tree))
    s = settings(catalog_server)
    annual_run(
        s,
        factory,
        fake,
        agents=True,
        store=MemoryStore(),
        crawler_kw={"clock": clock.time, "sleep": clock.sleep, "require_https": False},
    )
    with factory() as db:
        version = db.scalar(sa.select(m.ProgramVersion))
        assert (
            version is not None and version.status == "published" and version.checksum == "sha256:x"
        )
        item = db.scalar(
            sa.select(m.ReviewItem).where(m.ReviewItem.target_type == "program_version")
        )
        assert item is not None and item.diff["program_version_id"] is None
        assert "already published" in item.diff["blocked"]


def test_monthly_check_files_one_item_for_changed_pages(
    factory: Any, catalog_server: Any, clock: Any
) -> None:
    s = settings(catalog_server)
    kw = {"clock": clock.time, "sleep": clock.sleep, "require_https": False}
    store = MemoryStore()
    annual_run(s, factory, FakeLLM(), agents=False, store=store, crawler_kw=kw)
    assert monthly_check(s, factory, store=store, crawler_kw=kw) == 0
    page = catalog_server.root / "thecollege" / "fakehistory" / "index.html"
    page.write_text(page.read_text().replace("two FHIS courses", "three FHIS courses"))
    assert monthly_check(s, factory, store=store, crawler_kw=kw) == 1
    with factory() as db:
        item = db.scalar(
            sa.select(m.ReviewItem).where(m.ReviewItem.target_type == "catalog_change")
        )
        assert item is not None
        assert [c["url"] for c in item.diff["changed"]] == [
            f"{catalog_server.base_url}/thecollege/fakehistory/"
        ]
