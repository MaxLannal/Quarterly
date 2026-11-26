"""The planner agent's request and events (issue #17; docs/CONTRACTS.md "Planner agent").

One endpoint, `POST /agents/planner`, streams these events as Server-Sent Events, for a first
plan (`mode="generate"`) and for each chat message (`mode="chat"`).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from planner_core.models import ChangeOp, PlanState, TermId
from pydantic import BaseModel, ConfigDict, Field, RootModel

from api.schemas.agents import (
    ChatTurn,
    Citation,
    ConfirmEvent,
    DoneEvent,
    ErrorEvent,
    MessageEvent,
    StepEvent,
)

GroupKind = Literal["major", "core", "elective", "minor", "replace", "other"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionAnswer(_Strict):
    question_id: str = Field(max_length=48)
    #: The option the student picked (its label), or None for "Other".
    option: str | None = Field(default=None, max_length=200)
    #: The student's own words ("Other", or a list answer such as interests).
    text: str | None = Field(default=None, max_length=1000)


class PendingProposal(_Strict):
    """An open proposal of a plan that lives in the browser ("apply it" names the newest)."""

    group_id: str = Field(max_length=48)
    ops: list[ChangeOp] = Field(min_length=1, max_length=40)
    base_plan_hash: str = Field(max_length=80)


class PlannerRequest(_Strict):
    mode: Literal["generate", "chat"]
    plan: PlanState
    #: A saved plan of the logged-in account. Its chat, proposals and history live on the server.
    plan_id: uuid.UUID | None = None
    #: Chat mode: the student's message.
    message: str | None = Field(default=None, max_length=4000)
    #: Generate mode: continue a run that paused for a question, with the answer.
    run_id: uuid.UUID | None = None
    answer: QuestionAnswer | None = None
    #: A plan in the browser: the last turns of its chat, its open proposals, the General
    #: Information answers it holds (logged out) and its working information.
    history: list[ChatTurn] = Field(default=[], max_length=12)
    pending: list[PendingProposal] = Field(default=[], max_length=40)
    profile_answers: dict[str, Any] = Field(default={}, max_length=24)
    working_notes: str | None = Field(default=None, max_length=20_000)
    #: The current quarter: nothing is placed before it.
    today_term: TermId | None = None


class QuestionEvent(BaseModel):
    """The run paused: the page shows the question with its options and an "Other" box, and
    sends the answer back with `run_id`."""

    type: Literal["question"] = "question"
    run_id: str
    question_id: str
    #: The General Information field the answer fills, or None for the agent's own question.
    field: str | None = None
    text: str
    options: list[str] = []
    allow_other: bool = True


class PlanIssue(BaseModel):
    """A problem in the plan: a verifier issue (V01-V12) or a standard of the student that the
    planner checks itself (S01 a quarter away, S02 over the course load, S03 an avoided course)."""

    code: str
    level: Literal["error", "warning", "info"]
    message: str
    course_ids: list[str] = []
    term_ids: list[str] = []


class Compromise(BaseModel):
    """A guideline rule the plan bends, with what was traded."""

    rule: str
    tier: str
    why: str
    traded: str


class PlanEvent(BaseModel):
    """The whole proposed plan. `verdict` comes from Quarterly's verifier and certificate
    checker only; the model never sets it."""

    type: Literal["plan"] = "plan"
    run_id: str
    verdict: Literal["valid", "invalid"]
    issues: list[PlanIssue] = []
    compromises: list[Compromise] = []
    summary: str = ""


class RuleRef(BaseModel):
    """A guideline rule that a group follows, with its text for the chip."""

    id: str
    text: str


class IssueBrief(BaseModel):
    code: str
    level: str
    message: str


class Verdict(BaseModel):
    """The verifier's result on the plan after this proposal alone."""

    status_after: str
    status_before: str
    new_issues: list[IssueBrief] = []
    resolved_issues: int = 0


class PlannerProposalEvent(BaseModel):
    """One course or sequence, as an unsaved block on the grid. A saved plan has a
    `change_set_id` (Accept = POST /plans/{id}/changesets/{cs}/apply); a plan in the browser
    applies `ops` itself."""

    type: Literal["proposal"] = "proposal"
    change_set_id: str | None = None
    group_id: str
    title: str
    kind: GroupKind
    ops: list[ChangeOp]
    why: str
    citations: list[Citation] = []
    rules: list[RuleRef] = []
    preview: Verdict | None = None


PlannerEventItem = Annotated[
    StepEvent
    | QuestionEvent
    | PlanEvent
    | PlannerProposalEvent
    | MessageEvent
    | ConfirmEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]


class PlannerEvent(RootModel[PlannerEventItem]):
    """One Server-Sent Event `data:` payload from POST /agents/planner."""
