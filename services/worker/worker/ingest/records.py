"""What the pipeline produces, and the one place it is written to the database.

Agents never write: the pipeline collects `ReviewDraft`s (future `review_item` rows),
`VersionDraft`s (future `program_version` rows, always status `review`) and `RunRecord`s
(`extraction_run` rows), and `write_results` stores them. Nothing is published here: a
curator publishes from `/admin/review` (docs/CONTRACTS.md "Catalog ingestion").
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from llm_gateway.api import CallRecord

logger = logging.getLogger("worker.ingest")


@dataclass
class ReviewDraft:
    target_type: str  # program_version | course_batch | requisite | ingest_run | catalog_change
    target_id: str
    diff: dict[str, Any]
    reason: str


@dataclass
class VersionDraft:
    program_id: str
    name: str
    type: str
    degree: str | None
    department: str | None
    parent_id: str | None
    catalog_year: str
    rules: dict[str, Any]
    sources: list[dict[str, Any]]
    source_ids: list[int]
    checksum: str
    #: The review item that goes with this version (its target id is filled in on write).
    review: ReviewDraft


@dataclass
class RunRecord:
    """One agent extraction (`extraction_run`)."""

    kind: str  # e1 | e2 | e3 | e3b | e4
    model: str
    prompt_version: str
    input_snapshot_ids: list[str]
    output: dict[str, Any] | None
    status: str  # ok | failed | review
    cost_usd: float


@dataclass
class Results:
    reviews: list[ReviewDraft] = field(default_factory=list)
    versions: list[VersionDraft] = field(default_factory=list)
    runs: list[RunRecord] = field(default_factory=list)
    calls: list[CallRecord] = field(default_factory=list)

    def sink(self, record: CallRecord) -> None:
        self.calls.append(record)

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def extend(self, other: Results) -> None:
        self.reviews += other.reviews
        self.versions += other.versions
        self.runs += other.runs
        self.calls += other.calls


def _int_ids(ids: list[str]) -> list[int]:
    return [int(i) for i in ids if i.isdigit()]


def write_results(session: Any, results: Results) -> dict[str, int]:
    """Store drafts in one transaction. A version for a (program, year) that is already
    published is never touched: the proposal stays in its review item instead."""
    import sqlalchemy as sa
    from api.db import models as m

    today = dt.date.today()
    counts = {"review_items": 0, "program_versions": 0, "extraction_runs": 0, "llm_calls": 0}
    for run in results.runs:
        session.add(
            m.ExtractionRun(
                kind=run.kind[:32],
                model=run.model[:64],
                prompt_version=run.prompt_version[:32],
                input_snapshot_ids=_int_ids(run.input_snapshot_ids),
                output=run.output,
                status=run.status[:16],
                cost_usd=Decimal(f"{run.cost_usd:.4f}"),
            )
        )
        counts["extraction_runs"] += 1
    for call in results.calls:
        session.add(
            m.LlmCall(
                task=call.task[:48],
                model=call.model[:64],
                prompt_version=call.prompt_version[:32],
                in_tokens=call.in_tokens,
                out_tokens=call.out_tokens,
                cost_usd=Decimal(f"{call.cost_usd:.6f}"),
                latency_ms=call.latency_ms,
                ok=call.ok,
                created_day=today,
            )
        )
        counts["llm_calls"] += 1

    for v in results.versions:
        if session.get(m.CatalogYear, v.catalog_year) is None:
            session.add(m.CatalogYear(id=v.catalog_year))
            session.flush()
        if session.get(m.Program, v.program_id) is None:
            parent = v.parent_id if v.parent_id and session.get(m.Program, v.parent_id) else None
            session.add(
                m.Program(
                    id=v.program_id,
                    name=v.name,
                    type=v.type,
                    degree=v.degree,
                    department=v.department,
                    parent_id=parent,
                )
            )
            session.flush()
        row = session.scalar(
            sa.select(m.ProgramVersion).where(
                m.ProgramVersion.program_id == v.program_id,
                m.ProgramVersion.catalog_year == v.catalog_year,
            )
        )
        diff = dict(v.review.diff)
        if row is not None and row.status == "published":
            diff["program_version_id"] = None
            diff["blocked"] = (
                f"{v.program_id} {v.catalog_year} is already published; this proposal was not "
                "written to it"
            )
            target_id = f"{v.program_id}@{v.catalog_year}"
        else:
            if row is None:
                row = m.ProgramVersion(program_id=v.program_id, catalog_year=v.catalog_year)
                session.add(row)
            row.rules = v.rules
            row.status = "review"
            row.sources = v.sources
            row.source_ids = v.source_ids
            row.checksum = v.checksum
            row.verified_by = None
            row.verified_at = None
            session.flush()
            counts["program_versions"] += 1
            diff["program_version_id"] = row.id
            target_id = str(row.id)
            # Earlier open items for this version are superseded by the new run.
            session.execute(
                sa.update(m.ReviewItem)
                .where(
                    m.ReviewItem.target_type == "program_version",
                    m.ReviewItem.target_id == target_id,
                    m.ReviewItem.status == "open",
                )
                .values(status="rejected", reason="Superseded by a newer ingestion run.")
            )
        session.add(
            m.ReviewItem(
                target_type="program_version",
                target_id=target_id[:64],
                diff=diff,
                reason=v.review.reason,
                status="open",
            )
        )
        counts["review_items"] += 1

    for r in results.reviews:
        session.add(
            m.ReviewItem(
                target_type=r.target_type[:32],
                target_id=r.target_id[:64],
                diff=r.diff,
                reason=r.reason,
                status="open",
            )
        )
        counts["review_items"] += 1
    session.commit()
    logger.info("ingest: wrote %s", counts)
    return counts


class DbSnapshotLog:
    """`source_snapshot` rows, committed as they are fetched (ids are needed at once)."""

    def __init__(self, session_factory: Any) -> None:
        self.session_factory = session_factory

    def record(
        self,
        *,
        url: str,
        fetched_at: dt.datetime,
        sha256: str,
        storage_key: str,
        content_type: str | None,
    ) -> str:
        from api.db import models as m

        with self.session_factory() as session:
            row = m.SourceSnapshot(
                url=url,
                fetched_at=fetched_at,
                sha256=sha256,
                storage_key=storage_key,
                content_type=(content_type or "")[:128] or None,
            )
            session.add(row)
            session.commit()
            return str(row.id)
