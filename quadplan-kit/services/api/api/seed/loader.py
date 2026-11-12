"""Upsert a validated SeedBundle into Postgres. Idempotent: loading twice changes nothing."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from api.db import models as m
from api.seed.bundle import SeedBundle, build_catalog, build_requisites
from planner_core.hashing import sha256_of
from planner_core.terms import parse_term
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session


def _upsert(session: Session, table: Any, rows: list[dict[str, Any]], keys: list[str]) -> None:
    if not rows:
        return
    stmt = insert(table).values(rows)
    update = {c: stmt.excluded[c] for c in rows[0] if c not in keys}
    stmt = (
        stmt.on_conflict_do_update(index_elements=keys, set_=update)
        if update
        else stmt.on_conflict_do_nothing()
    )
    session.execute(stmt)


def upsert_bundle(session: Session, bundle: SeedBundle) -> dict[str, int]:
    year = bundle.catalog_year
    catalog = build_catalog(bundle)
    _upsert(session, m.CatalogYear, [{"id": year}], ["id"])
    _upsert(
        session,
        m.Term,
        [
            {
                "id": t.id,
                "year": parse_term(t.id)[0],
                "quarter": parse_term(t.id)[1],
                "start": t.start,
                "end": t.end,
            }
            for t in bundle.terms
        ],
        ["id"],
    )
    _upsert(
        session,
        m.Course,
        [
            {
                "catalog_year": year,
                "subject": c.code.split(" ")[0],
                "number": c.code.split(" ")[1],
                "code": c.code,
                "title": c.title,
                "units": c.units,
                "description": c.description,
                "notes": c.notes,
                "core_tags": c.core_tags,
                "tags": c.tags,
                "repeatable": c.repeatable,
                "source": c.source.model_dump(mode="json"),
                "needs_review": c.needs_review,
            }
            for c in bundle.courses
        ],
        ["catalog_year", "code"],
    )
    ids: dict[str, int] = dict(
        session.execute(
            sa.select(m.Course.code, m.Course.id).where(m.Course.catalog_year == year)
        ).all()
    )
    year_ids = list(ids.values())

    session.execute(sa.delete(m.CrosslistGroup).where(m.CrosslistGroup.course_id.in_(year_ids)))
    session.execute(sa.delete(m.CourseRelation).where(m.CourseRelation.course_a.in_(year_ids)))
    for group in catalog.crosslist_groups:
        session.execute(
            insert(m.CrosslistGroup).values(
                [{"group_id": f"{year}:{group[0]}", "course_id": ids[c]} for c in group]
            )
        )
    _upsert(
        session,
        m.CourseRelation,
        [
            {
                "course_a": ids[r.a],
                "course_b": ids[r.b],
                "kind": r.kind,
                "source": r.source.model_dump(mode="json") if r.source else None,
            }
            for r in catalog.relations
        ],
        ["course_a", "course_b", "kind"],
    )
    requisites = build_requisites(bundle)
    _upsert(
        session,
        m.Requisite,
        [
            {
                "course_id": ids[r.course],
                "catalog_year": year,
                "prereq": r.prereq.model_dump(mode="json") if r.prereq else None,
                "coreq": r.coreq.model_dump(mode="json") if r.coreq else None,
                "restrictions": r.restrictions.model_dump(mode="json") if r.restrictions else None,
                "raw_text": r.raw_text,
                "source": r.source.model_dump(mode="json") if r.source else None,
                "needs_review": r.needs_review,
            }
            for r in requisites
        ],
        ["course_id", "catalog_year"],
    )
    _upsert(
        session,
        m.OfferingPattern,
        [
            {
                "course_id": ids[o.course],
                "quarter": o.quarter,
                "p_offered": o.p_offered,
                "evidence_terms": o.evidence_terms,
                "method": o.method,
            }
            for o in catalog.offerings
        ],
        ["course_id", "quarter"],
    )
    _upsert(
        session,
        m.CourseList,
        [
            {
                "catalog_year": year,
                "name": cl.name,
                "label": cl.label,
                "course_ids": [ids[c] for c in cl.courses],
                "sublists": cl.sublists,
                "source": cl.source.model_dump(mode="json") if cl.source else None,
                "needs_review": cl.needs_review,
            }
            for cl in bundle.course_lists
        ],
        ["catalog_year", "name"],
    )
    for program in bundle.programs:
        _upsert(
            session,
            m.Program,
            [
                {
                    "id": program.id,
                    "name": program.name,
                    "type": program.type,
                    "degree": program.degree,
                    "department": program.department,
                    "parent_id": program.parent_id,
                }
            ],
            ["id"],
        )
    rows = []
    for program in bundle.programs:
        rules = program.rules_only()
        rows.append(
            {
                "program_id": program.id,
                "catalog_year": year,
                "rules": rules.model_dump(mode="json"),
                "status": program.status,
                "verified_by": program.verified_by,
                "verified_at": program.verified_at,
                "sources": [s.model_dump(mode="json") for s in program.sources],
                "checksum": sha256_of(rules),
            }
        )
    _upsert(session, m.ProgramVersion, rows, ["program_id", "catalog_year"])
    if bundle.college is not None:
        _upsert(
            session,
            m.CollegePolicy,
            [
                {
                    "catalog_year": year,
                    "rules": bundle.college.model_dump(mode="json"),
                    "status": "review",
                    "checksum": sha256_of(bundle.college),
                }
            ],
            ["catalog_year"],
        )
    session.commit()
    return {
        "terms": len(bundle.terms),
        "courses": len(bundle.courses),
        "crosslist_groups": len(catalog.crosslist_groups),
        "relations": len(catalog.relations),
        "requisites": len(requisites),
        "offering_patterns": len(catalog.offerings),
        "course_lists": len(bundle.course_lists),
        "programs": len(bundle.programs),
        "college_policy": int(bundle.college is not None),
    }
