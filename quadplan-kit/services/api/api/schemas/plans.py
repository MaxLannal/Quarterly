import datetime as dt
import uuid

from planner_core.models import ChangeOp, PlanState, Report, TermId, VerifyOptions
from pydantic import BaseModel, Field


class PlanSummary(BaseModel):
    id: uuid.UUID
    name: str
    catalog_year: str
    entry_term: str
    is_primary: bool
    updated_day: dt.date


class PlanOut(PlanSummary):
    state: PlanState
    plan_hash: str
    report: Report | None = None


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    state: PlanState
    is_primary: bool = False


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_primary: bool | None = None
    #: Replaces programs, goals, credits, placements and overload reasons; items change only
    #: through PATCH /plans/{id}/items.
    state: PlanState | None = None


class PlanImport(BaseModel):
    """Logged-out plans from localStorage, imported at login."""

    plans: list[PlanCreate] = Field(min_length=1, max_length=10)


class ItemsPatch(BaseModel):
    base_plan_hash: str
    ops: list[ChangeOp] = Field(min_length=1)


class ChangeSetApply(BaseModel):
    """Apply only if the plan still hashes to `base_plan_hash`. `confirmation_text` is the
    student's typed confirmation, parsed deterministically and matched against the ops."""

    base_plan_hash: str
    confirmation_text: str | None = None
    #: "Apply selected quarters": apply only ops whose term, from_term or to_term is listed.
    terms: list[TermId] | None = None


class PlanComparison(BaseModel):
    a: PlanOut
    b: PlanOut
    ops_a_to_b: list[ChangeOp] = []
    metrics: dict[str, dict[str, float]] = {}


class VerifyRequest(BaseModel):
    plan: PlanState
    options: VerifyOptions = VerifyOptions()
