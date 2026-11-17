"""`review_item` rows written by the schedule pipeline. Every kind starts with `schedule_`, so
they never clash with the catalog pipeline's kinds (prompt 09). The kind goes in
`target_type` and is repeated in `diff["kind"]`."""

from __future__ import annotations

from typing import Any, Final

import api.db.models as m
import sqlalchemy as sa
from sqlalchemy.orm import Session

UNKNOWN_CODE: Final = "schedule_unknown_code"
INSTRUCTOR_MATCH: Final = "schedule_instructor_match"
COUNT_ALERT: Final = "schedule_count_alert"
PARSER_REPAIR: Final = "schedule_parser_repair"
DEPT_PLAN: Final = "schedule_dept_plan"
KINDS: Final = (UNKNOWN_CODE, INSTRUCTOR_MATCH, COUNT_ALERT, PARSER_REPAIR, DEPT_PLAN)


def open_review(
    db: Session, kind: str, target_id: str, diff: dict[str, Any], reason: str
) -> m.ReviewItem:
    """Add a review item, or refresh the open one for the same kind and target (so a weekly
    re-run does not pile up duplicates). The caller commits."""
    assert kind in KINDS, kind
    target_id = target_id[:64]
    diff = {"kind": kind, **diff}
    item = db.scalar(
        sa.select(m.ReviewItem).where(
            m.ReviewItem.target_type == kind,
            m.ReviewItem.target_id == target_id,
            m.ReviewItem.status == "open",
        )
    )
    if item is None:
        item = m.ReviewItem(target_type=kind, target_id=target_id, diff=diff, reason=reason)
        db.add(item)
    else:
        item.diff = diff
        item.reason = reason
    db.flush()
    return item
