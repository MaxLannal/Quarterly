"""Review queue: list, decide, publish (SPEC "Human review and publish").

Every decision is a curator action by an admin; the pipeline only drafts. What a decision
does depends on the item's `target_type` (docs/CONTRACTS.md "Catalog ingestion"):

- `program_version`: accept marks it ready to publish; edit replaces the version's rules
  (validated, every node sourced); reject sends the version back to `draft`.
- `requisite`: accept writes the proposed prerequisite; edit writes the edited one; reject
  writes nothing.
- `course_batch`: accept writes the subject's courses, cross-lists, relations, offering
  pattern and prerequisites for the new catalog year; edit is not offered; reject writes
  nothing.
- anything else (`ingest_run`, `catalog_change`, other pipelines' items): the decision is
  recorded, and an edit keeps the edited content in the item.

Publishing a program version needs every review item about it decided, none rejected.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa
from fastapi import HTTPException
from planner_core.dsl import iter_nodes, iter_parts
from planner_core.hashing import sha256_of
from planner_core.models import Expr, ProgramRules
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.db import models as m
from api.schemas.admin import (
    ProgramVersionOut,
    ReviewCheck,
    ReviewDecision,
    ReviewItemOut,
    ReviewNode,
)
from api.schemas.common import Page
from api.seed.bundle import P_LISTED, P_UNLISTED

Status = str


def require_admin(account: m.Account) -> None:
    if account.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can use the review queue.")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail=detail)


def _version_id(item: m.ReviewItem) -> int | None:
    if item.target_type != "program_version":
        return None
    vid = item.diff.get("program_version_id")
    if isinstance(vid, int):
        return vid
    return int(item.target_id) if item.target_id.isdigit() else None


def _title(item: m.ReviewItem) -> str:
    d = item.diff
    year = d.get("catalog_year", "")
    match item.target_type:
        case "program_version":
            return f"{d.get('program_id', item.target_id)} {year}".strip()
        case "course_batch":
            return f"{d.get('subject', '')} courses {year}".strip()
        case "requisite":
            return f"Prerequisite of {d.get('course', item.target_id)} {year}".strip()
        case "ingest_run":
            return f"Ingestion {year}: {d.get('step', 'run')}".strip()
        case "catalog_change":
            return f"Catalog changes {year}".strip()
    return f"{item.target_type} {item.target_id}"


def _nodes(diff: dict[str, Any]) -> list[ReviewNode]:
    out = []
    for raw in diff.get("nodes") or []:
        try:
            out.append(ReviewNode.model_validate(raw))
        except ValidationError:
            continue
    return out


def _checks(diff: dict[str, Any]) -> list[ReviewCheck]:
    out = []
    for raw in diff.get("checks") or []:
        try:
            out.append(ReviewCheck.model_validate(raw))
        except ValidationError:
            continue
    return out


def to_out(db: Session, item: m.ReviewItem) -> ReviewItemOut:
    vid = _version_id(item)
    version = db.get(m.ProgramVersion, vid) if vid is not None else None
    status = item.status if item.status in ("open", "accepted", "rejected") else "open"
    return ReviewItemOut(
        id=item.id,
        target_type=item.target_type,
        target_id=item.target_id,
        diff=item.diff,
        reason=item.reason,
        status=status,
        decided_at=item.decided_at,
        title=_title(item),
        program_version_id=version.id if version is not None else None,
        program_version_status=version.status if version is not None else None,
        decision_hint=item.diff.get("decision_hint"),
        nodes=_nodes(item.diff),
        checks=_checks(item.diff),
    )


def list_items(db: Session, status: str | None, *, limit: int, offset: int) -> Page[ReviewItemOut]:
    query = sa.select(m.ReviewItem)
    count = sa.select(sa.func.count()).select_from(m.ReviewItem)
    if status is not None:
        query = query.where(m.ReviewItem.status == status)
        count = count.where(m.ReviewItem.status == status)
    rows = db.scalars(query.order_by(m.ReviewItem.id).limit(limit).offset(offset)).all()
    return Page(
        items=[to_out(db, r) for r in rows],
        total=db.scalar(count) or 0,
        limit=limit,
        offset=offset,
    )


# ------------------------------------------------------------------------- appliers


def _unsourced(rules: ProgramRules) -> list[str]:
    return [p for p, unit in [*iter_nodes(rules), *iter_parts(rules)] if unit.source is None]


def _valid_rules(raw: Any, version: m.ProgramVersion) -> ProgramRules:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="Send the edited rule tree as `edited.rules`.")
    raw = {"id": version.program_id, "catalog_year": version.catalog_year, **raw}
    try:
        rules = ProgramRules.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise HTTPException(
            status_code=422, detail=f"The rule tree is not valid: {where}: {first['msg']}"
        ) from exc
    if rules.id != version.program_id or rules.catalog_year != version.catalog_year:
        raise HTTPException(
            status_code=422, detail="The rule tree's id and catalog year must not change."
        )
    if missing := _unsourced(rules):
        raise HTTPException(
            status_code=422,
            detail=f"Every node needs a source quote; missing on {', '.join(missing[:5])}",
        )
    return rules


def _editable_version(db: Session, item: m.ReviewItem) -> m.ProgramVersion:
    vid = _version_id(item)
    version = db.get(m.ProgramVersion, vid) if vid is not None else None
    if version is None:
        raise _conflict(item.diff.get("blocked") or "This item has no program version to act on.")
    if version.status == "published":
        raise _conflict("This program version is already published.")
    return version


def _program_version(db: Session, item: m.ReviewItem, body: ReviewDecision) -> None:
    version = _editable_version(db, item)
    if body.decision == "reject":
        version.status = "draft"
    elif body.decision == "edit":
        rules = _valid_rules((body.edited or {}).get("rules"), version)
        version.rules = rules.model_dump(mode="json")
        version.checksum = sha256_of(rules)
        version.status = "review"
        item.diff = {
            **item.diff,
            "rules": version.rules,
            "edited": True,
            "nodes": [
                {
                    "path": path,
                    "kind": getattr(unit, "kind", "part"),
                    "label": unit.label,
                    "summary": "Edited by a curator",
                    "quote": unit.source.quote if unit.source else None,
                    "url": unit.source.url if unit.source else None,
                    "snapshot_id": unit.source.snapshot_id if unit.source else None,
                    "flags": [],
                }
                for path, unit in [*iter_nodes(rules), *iter_parts(rules)]
            ],
        }


def _course_id(db: Session, year: str, code: str) -> int:
    cid = db.scalar(
        sa.select(m.Course.id).where(m.Course.catalog_year == year, m.Course.code == code)
    )
    if cid is None:
        raise _conflict(f"{code} is not in the {year} catalog yet; accept its course batch first.")
    return cid


def _write_requisite(
    db: Session, year: str, code: str, expr: Expr, raw_text: str | None, source: Any
) -> None:
    stmt = insert(m.Requisite).values(
        course_id=_course_id(db, year, code),
        catalog_year=year,
        prereq=expr.model_dump(mode="json"),
        raw_text=raw_text,
        source=source,
        needs_review=False,
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["course_id", "catalog_year"],
            set_={
                "prereq": stmt.excluded.prereq,
                "raw_text": stmt.excluded.raw_text,
                "source": stmt.excluded.source,
                "needs_review": False,
            },
        )
    )


def _parse_expr(raw: Any) -> Expr:
    try:
        return Expr.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=f"The prerequisite is not valid: {exc.errors()[0]['msg']}"
        ) from exc


def _requisite(db: Session, item: m.ReviewItem, body: ReviewDecision) -> None:
    if body.decision == "reject":
        return
    d = item.diff
    raw = (body.edited or {}).get("prereq") if body.decision == "edit" else d.get("proposed")
    if raw is None:
        raise _conflict("There is no proposed prerequisite to accept; use edit to write one.")
    expr = _parse_expr(raw)
    _write_requisite(db, d["catalog_year"], d["course"], expr, d.get("raw_text"), d.get("source"))


def _course_batch(db: Session, item: m.ReviewItem, body: ReviewDecision) -> None:
    if body.decision == "edit":
        raise HTTPException(
            status_code=422,
            detail="Course batches cannot be edited here: accept or reject them, "
            "then fix single courses.",
        )
    if body.decision == "reject":
        return
    d = item.diff
    year = d["catalog_year"]
    if db.get(m.CatalogYear, year) is None:
        db.add(m.CatalogYear(id=year))
        db.flush()
    for c in d.get("courses", []):
        source = c.get("source") or {}
        sid = str(source.get("snapshot_id") or "")
        snapshot_id = int(sid) if sid.isdigit() else None
        if snapshot_id is not None and db.get(m.SourceSnapshot, snapshot_id) is None:
            snapshot_id = None
        values: dict[str, Any] = {
            "catalog_year": year,
            "subject": c["subject"],
            "number": c["number"],
            "code": c["code"],
            "title": c["title"],
            "units": c["units"],
            "description": c.get("description"),
            "notes": c.get("notes"),
            "source": {k: v for k, v in source.items() if k in ("url", "snapshot_id", "quote")},
            "source_id": snapshot_id,
        }
        stmt = insert(m.Course).values(**values)
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=["catalog_year", "code"],
                set_={k: stmt.excluded[k] for k in values if k not in ("catalog_year", "code")},
            )
        )
    ids = dict(
        db.execute(sa.select(m.Course.code, m.Course.id).where(m.Course.catalog_year == year)).all()
    )
    for c in d.get("courses", []):
        cid = ids[c["code"]]
        offered = c.get("terms_offered") or []
        quarters = ["AU", "WI", "SP"] + (["SU"] if "SU" in offered else []) if offered else []
        for q in quarters:
            p = P_LISTED if q in offered else P_UNLISTED
            stmt = insert(m.OfferingPattern).values(
                course_id=cid, quarter=q, p_offered=p, method="catalog"
            )
            db.execute(
                stmt.on_conflict_do_update(
                    index_elements=["course_id", "quarter"], set_={"p_offered": p}
                )
            )
    for group in d.get("crosslist_groups", []):
        members = [ids[code] for code in group if code in ids]
        if len(members) < 2:
            continue
        db.execute(sa.delete(m.CrosslistGroup).where(m.CrosslistGroup.course_id.in_(members)))
        db.execute(
            insert(m.CrosslistGroup).values(
                [{"group_id": f"{year}:{group[0]}", "course_id": i} for i in members]
            )
        )
    for rel in d.get("relations", []):
        if rel["a"] in ids and rel["b"] in ids:
            db.execute(
                insert(m.CourseRelation)
                .values(
                    course_a=ids[rel["a"]],
                    course_b=ids[rel["b"]],
                    kind=rel["kind"],
                    source=rel.get("source"),
                )
                .on_conflict_do_nothing()
            )
    for code, req in (d.get("requisites") or {}).items():
        if code in ids:
            _write_requisite(db, year, code, _parse_expr(req["prereq"]), req.get("raw_text"), None)


def _record_only(db: Session, item: m.ReviewItem, body: ReviewDecision) -> None:
    if body.decision == "edit":
        item.diff = {**item.diff, "edited_content": body.edited or {}}


APPLIERS: dict[str, Callable[[Session, m.ReviewItem, ReviewDecision], None]] = {
    "program_version": _program_version,
    "requisite": _requisite,
    "course_batch": _course_batch,
}


def decide(db: Session, admin: m.Account, item_id: int, body: ReviewDecision) -> ReviewItemOut:
    item = db.get(m.ReviewItem, item_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found.")
    if item.status != "open":
        raise _conflict(f"This item was already decided ({item.status}).")
    APPLIERS.get(item.target_type, _record_only)(db, item, body)
    item.status = "rejected" if body.decision == "reject" else "accepted"
    item.decided_by = admin.id
    item.decided_at = dt.date.today()
    if body.note:
        item.diff = {**item.diff, "curator_note": body.note}
    db.commit()
    db.refresh(item)
    return to_out(db, item)


def publish(db: Session, admin: m.Account, version_id: int) -> ProgramVersionOut:
    version = db.get(m.ProgramVersion, version_id, with_for_update=True)
    if version is None:
        raise HTTPException(status_code=404, detail="Program version not found.")
    if version.status == "published":
        raise _conflict("This program version is already published.")
    if version.status != "review":
        raise _conflict("Only a version in review can be published (this one was rejected).")
    items = db.scalars(
        sa.select(m.ReviewItem).where(
            m.ReviewItem.target_type == "program_version",
            m.ReviewItem.target_id == str(version_id),
        )
    ).all()
    if any(i.status == "open" for i in items):
        raise _conflict("Decide the open review items for this version first.")
    if items and all(i.status == "rejected" for i in items):
        raise _conflict("Every review of this version was rejected.")
    rules = _valid_rules(version.rules, version)
    version.checksum = sha256_of(rules)
    version.status = "published"
    version.verified_by = "curator"  # public on program pages: never an admin's username
    version.verified_at = dt.date.today()
    db.commit()
    return ProgramVersionOut(
        id=version.id,
        program_id=version.program_id,
        catalog_year=version.catalog_year,
        status="published",
        verified_by=version.verified_by,
        verified_at=version.verified_at,
        checksum=version.checksum,
    )
