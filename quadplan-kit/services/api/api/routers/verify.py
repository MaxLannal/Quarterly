from fastapi import APIRouter
from planner_core.models import Report

from api.schemas.common import NOT_IMPLEMENTED, not_implemented
from api.schemas.plans import VerifyRequest

router = APIRouter(tags=["verify"], responses=NOT_IMPLEMENTED)


@router.post("/verify", response_model=Report)
def verify_plan(body: VerifyRequest) -> Report:
    """Load the RuleSet for the plan's programs from Postgres, run planner_core.verify, cache the
    Report in Redis by plan_hash."""
    raise not_implemented("02")
