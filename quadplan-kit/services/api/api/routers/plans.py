import uuid

from fastapi import APIRouter, Response
from planner_core.models import ChangeSet

from api.schemas.common import NOT_IMPLEMENTED, not_implemented
from api.schemas.plans import (
    ChangeSetApply,
    ItemsPatch,
    PlanComparison,
    PlanCreate,
    PlanImport,
    PlanOut,
    PlanSummary,
    PlanUpdate,
)

router = APIRouter(prefix="/plans", tags=["plans"], responses=NOT_IMPLEMENTED)


@router.get("", response_model=list[PlanSummary])
def list_plans() -> list[PlanSummary]:
    raise not_implemented("04/06")


@router.post("", response_model=PlanOut, status_code=201)
def create_plan(body: PlanCreate) -> PlanOut:
    raise not_implemented("04/06")


@router.post("/import", response_model=list[PlanSummary])
def import_plans(body: PlanImport) -> list[PlanSummary]:
    raise not_implemented("04/06")


@router.get("/compare", response_model=PlanComparison)
def compare_plans(a: uuid.UUID, b: uuid.UUID) -> PlanComparison:
    raise not_implemented("06")


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: uuid.UUID) -> PlanOut:
    raise not_implemented("04/06")


@router.patch("/{plan_id}", response_model=PlanOut)
def update_plan(plan_id: uuid.UUID, body: PlanUpdate) -> PlanOut:
    raise not_implemented("04/06")


@router.delete("/{plan_id}", status_code=204, response_class=Response)
def delete_plan(plan_id: uuid.UUID) -> None:
    raise not_implemented("04/06")


@router.post("/{plan_id}/duplicate", response_model=PlanOut, status_code=201)
def duplicate_plan(plan_id: uuid.UUID) -> PlanOut:
    raise not_implemented("04/06")


@router.patch("/{plan_id}/items", response_model=PlanOut)
def patch_items(plan_id: uuid.UUID, body: ItemsPatch) -> PlanOut:
    raise not_implemented("04/06")


@router.get("/{plan_id}/changesets", response_model=list[ChangeSet])
def list_change_sets(plan_id: uuid.UUID) -> list[ChangeSet]:
    raise not_implemented("06")


@router.post("/{plan_id}/changesets/{changeset_id}/apply", response_model=PlanOut)
def apply_change_set(plan_id: uuid.UUID, changeset_id: uuid.UUID, body: ChangeSetApply) -> PlanOut:
    raise not_implemented("06")


@router.post("/{plan_id}/changesets/{changeset_id}/discard", response_model=ChangeSet)
def discard_change_set(plan_id: uuid.UUID, changeset_id: uuid.UUID) -> ChangeSet:
    raise not_implemented("06")
