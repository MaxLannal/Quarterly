import datetime as dt
import uuid

from planner_core.models import (
    ChangeOp,
    ChangeSet,
    GenerateOptions,
    Infeasibility,
    PlanState,
    Report,
    TermId,
    VerifyOptions,
)
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
    #: Saves the whole plan: items (kept by id), programs, goals, credits, placements and
    #: overload reasons. Small edits can go through PATCH /plans/{id}/items instead.
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


class GeneratedVariant(BaseModel):
    """One generated plan: a proposed change set plus the verified plan it leads to."""

    label: str
    change_set: ChangeSet
    plan: PlanState
    report: Report
    metrics: dict[str, float] = {}
    rationale: dict[str, str] = {}


class GenerateOut(BaseModel):
    variants: list[GeneratedVariant] = []
    #: Set when no plan meets the request: the smallest set of goals to relax, in plain English.
    infeasible: Infeasibility | None = None


class GenerateLocal(BaseModel):
    """Generate for a plan that lives only in the browser (logged out, or not saved yet)."""

    plan: PlanState
    options: GenerateOptions = GenerateOptions()
