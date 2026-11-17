"""The catalog's scheduled jobs (SPEC: "each new catalog year, plus a monthly change check").

Both are off unless `CATALOG_INGEST_ENABLED=true`: `cron_jobs()` registers nothing, and the
job functions return "disabled" even when called by hand.

- `annual_run` (1 August, 04:00): crawl, parse courses, E1, E2, E3/E3b/E4 for every program,
  diff against last year's published versions, write review items and `review` versions.
  The agents run only with `LLM_LIVE=true`, behind `INGEST_COST_CAP_USD`.
- `monthly_check` (the 15th, 04:00): re-fetch the newest year's catalog pages and compare their
  sha256 with the last snapshots; changed pages become one `catalog_change` review item. No
  model is called.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Any

from worker.ingest.records import DbSnapshotLog, Results, ReviewDraft, write_results
from worker.ingest.settings import IngestSettings, get_ingest_settings

logger = logging.getLogger("worker.ingest")

ROOT = Path(__file__).resolve().parents[4]


def next_year(year: str) -> str:
    start = int(year[:4]) + 1
    return f"{start}-{str(start + 1)[2:]}"


def _archive(settings: IngestSettings, factory: Any, store: Any = None) -> Any:
    from worker.ingest.snapshots import MinioStore, SnapshotArchive

    store = store or MinioStore(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password.get_secret_value(),
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )
    return SnapshotArchive(store, DbSnapshotLog(factory))


def _crawler(settings: IngestSettings, archive: Any, client: Any = None, **kw: Any) -> Any:
    import urllib.parse

    from worker.ingest.crawler import Crawler

    hosts = {
        urllib.parse.urlsplit(settings.catalog_base_url).netloc,
        urllib.parse.urlsplit(settings.catalog_counts_url).netloc,
    }
    return Crawler(
        archive=archive,
        contact=settings.catalog_contact_email,
        allowed_hosts={h for h in hosts if h},
        interval_s=settings.catalog_request_interval_s,
        client=client,
        **kw,
    )


def newest_year(session: Any) -> str | None:
    import sqlalchemy as sa
    from api.db import models as m

    years = sorted(session.scalars(sa.select(m.CatalogYear.id)))
    return years[-1] if years else None


def published_programs(session: Any, year: str) -> dict[str, Any]:
    import sqlalchemy as sa
    from api.db import models as m
    from planner_core.models import ProgramRules

    rows = session.scalars(
        sa.select(m.ProgramVersion).where(
            m.ProgramVersion.catalog_year == year, m.ProgramVersion.status == "published"
        )
    )
    return {r.program_id: ProgramRules.model_validate(r.rules) for r in rows}


def annual_run(
    settings: IngestSettings,
    factory: Any,
    llm: Any,
    *,
    agents: bool,
    store: Any = None,
    client: Any = None,
    crawler_kw: dict[str, Any] | None = None,
) -> dict[str, int]:
    from api.seed.bundle import load_bundle

    from worker.ingest.catalog import from_db
    from worker.ingest.courses import previous_from_db
    from worker.ingest.crawler import crawl_catalog
    from worker.ingest.golden import golden_runner
    from worker.ingest.llm import Metered
    from worker.ingest.pipeline import AnnualInputs, run_annual

    with factory() as session:
        previous = newest_year(session)
        target = settings.catalog_target_year or (next_year(previous) if previous else "")
        if not re.match(r"^\d{4}-\d{2}$", target):
            raise ValueError("set CATALOG_TARGET_YEAR (no catalog year in the database yet)")
        prev_courses = previous_from_db(session, previous) if previous else {}
        prev_programs = published_programs(session, previous) if previous else {}
        lists = list(from_db(session, previous).lists.values()) if previous else []

    archive = _archive(settings, factory, store)
    crawl = crawl_catalog(
        _crawler(settings, archive, client, **(crawler_kw or {})),
        settings.catalog_base_url,
        counts_url=settings.catalog_counts_url,
    )
    seed_dir = ROOT / "data" / "seed" / (previous or "")
    golden = (
        golden_runner(load_bundle(seed_dir), ROOT / "data" / "golden")
        if previous and seed_dir.is_dir()
        else None
    )
    metered = Metered(llm, cap_usd=settings.ingest_cost_cap_usd)
    results = run_annual(
        metered,
        AnnualInputs(
            catalog_year=target,
            previous_year=previous,
            crawl=crawl,
            previous_courses=prev_courses,
            previous_programs=prev_programs,
            course_lists=lists,
            golden=golden,
            agents=agents,
        ),
    )
    results.calls += metered.records
    if crawl.skipped:
        results.reviews.append(
            ReviewDraft(
                "ingest_run",
                f"{target}:crawl",
                {
                    "kind": "ingest_run",
                    "catalog_year": target,
                    "step": "crawl",
                    "problems": [f"{s.url}: {s.reason}" for s in crawl.skipped],
                },
                f"{len(crawl.skipped)} page(s) were not fetched",
            )
        )
    with factory() as session:
        return write_results(session, results)


def monthly_check(
    settings: IngestSettings,
    factory: Any,
    *,
    store: Any = None,
    client: Any = None,
    crawler_kw: dict[str, Any] | None = None,
) -> int:
    """Number of changed pages (0: nothing written)."""
    import sqlalchemy as sa
    from api.db import models as m

    from worker.ingest.crawler import crawl_catalog

    host = settings.catalog_base_url.rstrip("/")
    with factory() as session:
        year = newest_year(session) or "unknown"
        rows = session.execute(
            sa.select(m.SourceSnapshot.url, m.SourceSnapshot.sha256, m.SourceSnapshot.id)
            .where(m.SourceSnapshot.url.startswith(host))
            .order_by(m.SourceSnapshot.id)
        ).all()
    last = {r.url: r.sha256 for r in rows}  # the newest row per URL wins
    known = set(last)
    archive = _archive(settings, factory, store)
    crawler = _crawler(settings, archive, client, **(crawler_kw or {}))
    crawl = crawl_catalog(crawler, settings.catalog_base_url, only=known)
    changed = []
    for snap in crawl.all_snapshots():
        before = last.get(snap.url)
        if before is not None and before != snap.sha256:
            changed.append(
                {"url": snap.url, "before": before, "after": snap.sha256, "snapshot_id": snap.id}
            )
    listed = set(crawl.index_urls + crawl.az_urls) - known
    new = sorted(u for u in listed if crawler.allowed(u))
    if not changed and not new:
        return 0
    today = dt.date.today().isoformat()
    review = ReviewDraft(
        "catalog_change",
        f"{year}:{today}",
        {"kind": "catalog_change", "catalog_year": year, "changed": changed, "new_pages": new},
        f"{len(changed)} catalog page(s) changed and {len(new)} new page(s) appeared since "
        "the last "
        "fetch. Look at the changes and decide whether to re-run the ingestion for those programs.",
    )
    with factory() as session:
        write_results(session, Results(reviews=[review]))
    return len(changed) + len(new)


# ----------------------------------------------------------------------------- Arq


def _factory() -> Any:
    from api.db.session import get_engine
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(get_engine())


async def catalog_annual(ctx: dict[str, Any]) -> str:
    import asyncio

    settings = get_ingest_settings()
    if not settings.catalog_ingest_enabled:
        return "disabled (CATALOG_INGEST_ENABLED is off)"

    def run() -> str:
        from api.agents.llm import configure_llm
        from api.config import get_settings
        from llm_gateway.api import get_llm

        live = configure_llm(get_settings())
        counts = annual_run(settings, _factory(), get_llm(), agents=live)
        return f"annual catalog run: {counts}"

    return await asyncio.to_thread(run)


async def catalog_monthly(ctx: dict[str, Any]) -> str:
    import asyncio

    settings = get_ingest_settings()
    if not settings.catalog_ingest_enabled:
        return "disabled (CATALOG_INGEST_ENABLED is off)"
    changed = await asyncio.to_thread(monthly_check, settings, _factory())
    return f"monthly catalog check: {changed} change(s)"


def cron_jobs(settings: IngestSettings | None = None) -> list[Any]:
    """The catalog cron jobs, or none when CATALOG_INGEST_ENABLED is off."""
    from arq import cron

    settings = settings or get_ingest_settings()
    if not settings.catalog_ingest_enabled:
        return []
    return [
        cron(
            catalog_annual,
            month={8},
            day={1},
            hour={4},
            minute={0},
            run_at_startup=False,
            timeout=6 * 3600,
        ),
        cron(catalog_monthly, day={15}, hour={4}, minute={0}, run_at_startup=False, timeout=3600),
    ]
