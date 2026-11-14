"""Small helpers on stored A3 output, shared by the nightly job and the forum code (no model
imports here, so the forum can use them without import cycles)."""

from __future__ import annotations

from collections.abc import Collection

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.db import models as m


def cited_ids(row: m.ForumSummary) -> list[int]:
    """The post ids a summary cites, in its [n] order."""
    return [
        c if isinstance(c, int) else int(c.get("post_id", 0))
        for c in row.citations or []
        if isinstance(c, int) or (isinstance(c, dict) and "post_id" in c)
    ]


def hidden_citations(db: Session, row: m.ForumSummary) -> bool:
    """True when the summary cites a post that is no longer visible (held, removed or
    deleted). Such a summary is not shown, and the nightly job deletes and rewrites it."""
    ids = set(cited_ids(row))
    if not ids:
        return False
    visible = db.scalar(
        sa.select(sa.func.count()).where(m.Post.id.in_(ids), m.Post.status == "visible")
    )
    return (visible or 0) < len(ids)


def forget_extractions(db: Session, post_ids: Collection[int]) -> None:
    """Delete the stored A3 extractions (they hold word-for-word quotes) of these posts: called
    when a post is deleted, blanked or edited."""
    if post_ids:
        db.execute(
            sa.delete(m.ExtractionRun).where(
                m.ExtractionRun.kind == "a3_extraction",
                m.ExtractionRun.output["post_id"].as_integer().in_(list(post_ids)),
            )
        )
