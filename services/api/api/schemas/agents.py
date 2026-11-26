from typing import Annotated, Any, Literal

from planner_core.models import ChangeSet, Conflict, Goal, PlanState, Report, TermId
from pydantic import BaseModel, Field, RootModel


class GenerateRequest(BaseModel):
    """The Generate-plan popup: a form, never free text (SPEC "Generate-plan popup")."""

    #: A saved plan of the logged-in account. When the plan below still matches it, each
    #: variant is stored as a proposed change set; otherwise nothing is saved.
    plan_id: str | None = None
    plan: PlanState
    scope: Literal["whole", "remaining", "selected"] = "whole"
    selected_terms: list[str] = []
    #: The current quarter: nothing is placed before it ("remaining" starts here).
    today_term: TermId | None = None
    #: Career-wide load slider: -1 lighter ... +1 heavier.
    load: float = Field(default=0.0, ge=-1, le=1)
    per_term_load: dict[str, float] = {}
    max_courses_per_term: int | None = Field(default=None, ge=1, le=6)
    allow_overload: bool = False
    goals: list[Goal] = []
    interests: list[Annotated[str, Field(max_length=60)]] = Field(default=[], max_length=12)
    variants: int = Field(default=2, ge=1, le=3)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    #: A saved plan of the logged-in account, unchanged since it was saved. The chat history
    #: and proposals of a saved plan live on the server.
    plan_id: str | None = None
    plan: PlanState
    run_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    #: Earlier turns of this conversation, for a plan that is not saved (ignored otherwise).
    history: list[ChatTurn] = Field(default=[], max_length=12)
    #: The newest proposal card not yet applied or dismissed, for a plan that is not saved
    #: ("apply it" refers to it). A saved plan's proposals are read from the server.
    latest_proposal: ChangeSet | None = None


class Citation(BaseModel):
    #: `profile` = a General Information field of the student (the chip links to it on the
    #: dashboard); `guideline` = a rule of data/planner/plan-guideline.md (issue #17).
    kind: Literal["attribute", "post", "course", "program", "summary", "profile", "guideline"]
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
    #: term -> one-line rationale (at most 25 words); empty when the rationale step failed.
    rationale: dict[str, str] = {}
    citations: list[Citation] = []
    metrics: dict[str, float] = {}


class InfeasibleEvent(BaseModel):
    """No plan meets the request; `message` says why in plain English."""

    type: Literal["infeasible"] = "infeasible"
    message: str
    conflicts: list[Conflict] = []


class MessageEvent(BaseModel):
    type: Literal["message"] = "message"
    text: str
    citations: list[Citation] = []


class ProposalEvent(BaseModel):
    type: Literal["proposal"] = "proposal"
    change_set: ChangeSet


class ConfirmEvent(BaseModel):
    """The student's message was a typed confirmation of `change_set`. A saved plan applies
    it with POST /plans/{id}/changesets/{cs}/apply and `confirmation_text`; a plan that lives
    in the browser applies the operations itself."""

    type: Literal["confirm"] = "confirm"
    change_set: ChangeSet
    confirmation_text: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    run_id: str
    #: The planner chat noted a preference for a plan in the browser: its whole working
    #: information, to store with the plan (a saved plan's record is updated on the server).
    working_notes: str | None = None
    #: A plan in the browser answered a General Information question in this run: the answers
    #: as their fields store them, to keep with the plan (and copy to the record at login).
    profile_answers: dict[str, Any] | None = None


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    #: `expired`: the paused run is gone (start again); `unavailable`: the AI is off or failed.
    reason: Literal["expired", "unavailable", "invalid_output", "budget", "invalid_plan"] | None = (
        None
    )


class AgentEvent(
    RootModel[
        Annotated[
            StepEvent
            | VariantEvent
            | InfeasibleEvent
            | MessageEvent
            | ProposalEvent
            | ConfirmEvent
            | DoneEvent
            | ErrorEvent,
            Field(discriminator="type"),
        ]
    ]
):
    """One Server-Sent Event `data:` payload from /agents/generate or /agents/chat."""


class ChatEntry(BaseModel):
    role: Literal["user", "assistant", "proposal"]
    text: str = ""
    citations: list[Citation] = []
    change_set: ChangeSet | None = None


class ChatHistory(BaseModel):
    """A saved plan's advisor conversation of the last 30 days, oldest first."""

    run_id: str | None = None
    entries: list[ChatEntry] = []
