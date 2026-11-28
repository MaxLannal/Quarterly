"""Shared agent models: chat turns, citations and the common Server-Sent Events. The planner
agent's own request and events are in `api.schemas.planner`."""

from typing import Any, Literal

from planner_core.models import ChangeSet
from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=4000)


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


class MessageEvent(BaseModel):
    type: Literal["message"] = "message"
    text: str
    citations: list[Citation] = []


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
    #: The math placement the student gave the planner (course codes): the page adds each as a
    #: placement credit to the plan, which is the plan the run's proposals were made for.
    placements: list[str] | None = None


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    #: `expired`: the paused run is gone (start again); `unavailable`: the AI is off or failed.
    reason: Literal["expired", "unavailable", "invalid_output", "budget", "invalid_plan"] | None = (
        None
    )


class ChatEntry(BaseModel):
    role: Literal["user", "assistant", "proposal"]
    text: str = ""
    citations: list[Citation] = []
    change_set: ChangeSet | None = None
    #: A planner proposal's group: {group_id, title, kind, why, citations, rules}.
    meta: dict[str, Any] | None = None


class ChatHistory(BaseModel):
    """A saved plan's planner conversation, oldest first (kept while the plan exists)."""

    run_id: str | None = None
    entries: list[ChatEntry] = []
