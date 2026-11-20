from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from api.auth.sessions import current_account
from api.commons import moderation as commons_moderation
from api.db.models import Account
from api.db.session import get_session
from api.forum import admin as forum_admin
from api.review import service as review
from api.schemas.admin import ProgramVersionOut, ReviewDecision, ReviewItemOut
from api.schemas.common import NOT_IMPLEMENTED, Page
from api.schemas.commons import (
    CommonsModerationDecision,
    CommonsModerationItem,
    CommonsModerationResult,
)
from api.schemas.forum import (
    EndSuspensionResult,
    ModerationDecision,
    ModerationItemOut,
    ModerationResult,
    SuspensionOut,
)

router = APIRouter(prefix="/admin", tags=["admin"], responses=NOT_IMPLEMENTED)


# ------------------------------------------------------------------ Forum moderation (08)


def _admin(account: Annotated[Account, Depends(current_account)], response: Response) -> Account:
    forum_admin.require_admin(account)
    response.headers["Cache-Control"] = "private, no-store"
    return account


AdminDep = Annotated[Account, Depends(_admin)]
SessionDep = Annotated[Session, Depends(get_session)]


# Held posts and comments, and everything with an open report, oldest first.
@router.get("/moderation", response_model=Page[ModerationItemOut])
def moderation_queue(
    db: SessionDep,
    _: AdminDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ModerationItemOut]:
    return forum_admin.queue(db, limit=limit, offset=offset)


@router.post("/moderation/{target_type}/{target_id}/decision", response_model=ModerationResult)
def moderation_decision(
    db: SessionDep,
    admin: AdminDep,
    target_type: Literal["post", "comment"],
    target_id: int,
    body: ModerationDecision,
) -> ModerationResult:
    return forum_admin.decide(db, admin, target_type, target_id, body)


# Active suspensions (each shown by the removal that started it) and ending one early.
@router.get("/moderation/suspensions", response_model=list[SuspensionOut])
def moderation_suspensions(db: SessionDep, _: AdminDep) -> list[SuspensionOut]:
    return forum_admin.suspensions(db)


@router.post(
    "/moderation/{target_type}/{target_id}/end-suspension", response_model=EndSuspensionResult
)
def moderation_end_suspension(
    db: SessionDep, admin: AdminDep, target_type: Literal["post", "comment"], target_id: int
) -> EndSuspensionResult:
    return forum_admin.end_suspension(db, admin, target_type, target_id)


# ---------------------------------------------------------------- Review queue (09)


def _reviewer(account: Annotated[Account, Depends(current_account)], response: Response) -> Account:
    review.require_admin(account)
    response.headers["Cache-Control"] = "private, no-store"
    return account


ReviewerDep = Annotated[Account, Depends(_reviewer)]


# Items the pipelines drafted (ingestion, schedule, ...), oldest first.
@router.get("/review-items", response_model=Page[ReviewItemOut])
def list_review_items(
    db: SessionDep,
    _: ReviewerDep,
    status: Literal["open", "accepted", "rejected"] | None = "open",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ReviewItemOut]:
    return review.list_items(db, status, limit=limit, offset=offset)


@router.post("/review-items/{item_id}/decision", response_model=ReviewItemOut)
def decide_review_item(
    db: SessionDep, admin: ReviewerDep, item_id: int, body: ReviewDecision
) -> ReviewItemOut:
    return review.decide(db, admin, item_id, body)


# Publishing is the only way a program version reaches students.
@router.post("/program-versions/{version_id}/publish", response_model=ProgramVersionOut)
def publish_program_version(
    db: SessionDep, admin: ReviewerDep, version_id: int
) -> ProgramVersionOut:
    return review.publish(db, admin, version_id)


# ------------------------------------------------------------------ Commons moderation (CC-7)


# Reported Commons questions and replies, oldest report first.
@router.get("/commons-reports", response_model=list[CommonsModerationItem])
def commons_reports(db: SessionDep, _: AdminDep) -> list[CommonsModerationItem]:
    return commons_moderation.queue(db)


# Remove (shown as "[removed]", replies under it stay) or keep; the open reports close.
@router.post(
    "/commons-reports/{target_type}/{target_id}/decision",
    response_model=CommonsModerationResult,
)
def commons_report_decision(
    db: SessionDep,
    admin: AdminDep,
    target_type: Literal["thread", "reply"],
    target_id: int,
    body: CommonsModerationDecision,
) -> CommonsModerationResult:
    return commons_moderation.decide(db, admin, target_type, target_id, body)
