from typing import Annotated, Literal

from planner_core.models import ChangeSet, Goal, PlanState, Report
from pydantic import BaseModel, Field, RootModel


class GenerateRequest(BaseModel):
    """The Generate-plan popup: a form, never free text (SPEC "Generate-plan popup")."""

    plan_id: str | None = None
    plan: PlanState
    scope: Literal["whole", "remaining", "selected"] = "whole"
    selected_terms: list[str] = []
    #: Career-wide load slider: -1 lighter ... +1 heavier.
    load: float = Field(default=0.0, ge=-1, le=1)
    per_term_load: dict[str, float] = {}
    max_courses_per_term: int | None = Field(default=None, ge=1, le=6)
    allow_overload: bool = False
    goals: list[Goal] = []
    interests: list[str] = []
    variants: int = Field(default=2, ge=1, le=3)


class ChatRequest(BaseModel):
    plan_id: str | None = None
    plan: PlanState
    run_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)


class Citation(BaseModel):
    kind: Literal["attribute", "post", "course", "program", "summary"]
    id: str
    label: str


class StepEvent(BaseModel):
    type: Literal["step"] = "step"
    name: str
    status: Literal["started", "done", "failed"]


class VariantEvent(BaseModel):
    type: Literal["variant"] = "variant"
    label: str
    change_set: ChangeSet
    report: Report
    rationale: dict[str, str] = {}
    metrics: dict[str, float] = {}


class MessageEvent(BaseModel):
    type: Literal["message"] = "message"
    text: str
    citations: list[Citation] = []


class ProposalEvent(BaseModel):
    type: Literal["proposal"] = "proposal"
    change_set: ChangeSet


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    run_id: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class AgentEvent(
    RootModel[
        Annotated[
            StepEvent | VariantEvent | MessageEvent | ProposalEvent | DoneEvent | ErrorEvent,
            Field(discriminator="type"),
        ]
    ]
):
    """One Server-Sent Event `data:` payload from /agents/generate or /agents/chat."""
