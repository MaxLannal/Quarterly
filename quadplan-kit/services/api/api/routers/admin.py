from typing import Literal

from fastapi import APIRouter, Query

from api.schemas.admin import ProgramVersionOut, ReviewDecision, ReviewItemOut
from api.schemas.common import NOT_IMPLEMENTED, Page, not_implemented

router = APIRouter(prefix="/admin", tags=["admin"], responses=NOT_IMPLEMENTED)


@router.get("/review-items", response_model=Page[ReviewItemOut])
def list_review_items(
    status: Literal["open", "accepted", "rejected"] | None = "open",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ReviewItemOut]:
    raise not_implemented("09")


@router.post("/review-items/{item_id}/decision", response_model=ReviewItemOut)
def decide_review_item(item_id: int, body: ReviewDecision) -> ReviewItemOut:
    raise not_implemented("09")


@router.post("/program-versions/{version_id}/publish", response_model=ProgramVersionOut)
def publish_program_version(version_id: int) -> ProgramVersionOut:
    raise not_implemented("09")
