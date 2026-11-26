"""The planner agent's saved run state and the payloads of its submit tools."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from api.schemas.planner import GroupKind, QuestionAnswer


class AskedQuestion(BaseModel):
    question_id: str
    #: The General Information field the answer fills; None for the agent's own question.
    field: str | None = None
    text: str
    options: list[str] = []


class RunState(BaseModel):
    """`agent_run.state` of a run that paused for an answer (issue #17 step 12)."""

    phase: Literal["ask", "fill"] = "ask"
    asked: list[AskedQuestion] = []
    answers: dict[str, QuestionAnswer] = {}
    #: The model already wrote its questions (it asks once per run).
    model_asked: bool = False
    day: dt.date


# ----------------------------------------------------------------------------- submit tools


class QuestionIn(BaseModel):
    id: str = Field(max_length=8)
    question: str = Field(max_length=300)
    options: list[str] = Field(max_length=5)
    decision: str = Field(default="", max_length=300)
    why: str = Field(default="", max_length=300)


class QuestionsSubmission(BaseModel):
    questions: list[QuestionIn] = []


class GroupCourse(BaseModel):
    code: str = Field(max_length=16)
    term: str = Field(max_length=7)


class GroupIn(BaseModel):
    id: str = Field(max_length=16)
    title: str = Field(max_length=80)
    kind: GroupKind
    courses: list[GroupCourse] = Field(min_length=1, max_length=20)
    why: str = Field(max_length=800)
    rules: list[str] = Field(default=[], max_length=8)


class PlanSubmission(BaseModel):
    groups: list[GroupIn] = Field(min_length=1, max_length=24)
    notes: str = Field(default="", max_length=600)


class RepairOp(BaseModel):
    op: Literal["add", "move", "remove"]
    course: str = Field(max_length=16)
    term: str = ""
    from_term: str = ""
    to_term: str = ""
    why: str = ""
    #: The group an added course joins (empty: the group of the course it replaces, or new).
    group_id: str = ""


class Bend(BaseModel):
    rule: str
    tier: str = ""
    why: str = ""
    traded: str = ""


class RepairSubmission(BaseModel):
    summary: str = Field(default="", max_length=400)
    ops: list[RepairOp] = []
    bent: list[Bend] = []


class ExplainedGroup(BaseModel):
    id: str
    why: str = Field(max_length=800)
    citations: list[str] = []


class ExplanationsSubmission(BaseModel):
    groups: list[ExplainedGroup] = []
