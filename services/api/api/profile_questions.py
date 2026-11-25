"""The General Information questions (Issue #14), read from data/profile/questions.yaml.

That file is the only place the questions are written: the registration form and the dashboard
get them from `GET /profile/questions`, the dashboard agent and `render_student_md()` from
`question_set()` here. A question's `options` are fixed; the agent may reword `text` only.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

QUESTIONS_FILE = Path(__file__).resolve().parents[3] / "data" / "profile" / "questions.yaml"

QuestionType = Literal["single", "multi", "scale", "list", "table"]
ValueType = Literal["integer", "boolean", "term", "program", "text", "course"]
OptionValue = bool | int | str


class QuestionOption(BaseModel):
    value: OptionValue
    label: str


class QuestionColumn(BaseModel):
    id: str
    label: str
    options: list[str] = []


class ScaleEnds(BaseModel):
    min: str
    max: str


class Question(BaseModel):
    id: str = Field(pattern=r"^[a-z_]+$", max_length=40)
    group: str
    field: str
    #: A short name for the answer ("Class year"): the dashboard and student.md show it.
    label: str
    text: str
    type: QuestionType
    options: list[QuestionOption] = []
    step: Literal[1, 2]
    value: ValueType = "text"
    min: int | None = None
    max: int | None = None
    ends: ScaleEnds | None = None
    #: Asked only when every named field has this value (`transfer_or_later` is the
    #: registration form's checkbox, not a stored field).
    when: dict[str, bool] | None = None
    columns: list[QuestionColumn] = []
    help: str | None = None

    def label_of(self, value: object) -> str | None:
        """The label of an option value (None when it is not one of the options)."""
        for option in self.options:
            if option.value == value and type(option.value) is type(value):
                return option.label
        return None


class QuestionGroup(BaseModel):
    id: str
    title: str


class QuestionSet(BaseModel):
    version: int
    groups: list[QuestionGroup]
    questions: list[Question]
    #: Labels for the values of table columns: {kind: {AP: "AP", ...}, status: ..., away: ...}.
    labels: dict[str, dict[str, str]] = {}

    @model_validator(mode="after")
    def _consistent(self) -> QuestionSet:
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("question ids must be unique")
        groups = {g.id for g in self.groups}
        for q in self.questions:
            if q.group not in groups:
                raise ValueError(f"{q.id}: unknown group {q.group!r}")
            if q.type == "single" and q.value not in ("term", "program") and not q.options:
                raise ValueError(f"{q.id}: a single-choice question needs options")
        return self

    def question(self, question_id: str) -> Question | None:
        return next((q for q in self.questions if q.id == question_id), None)

    def step(self, step: int) -> list[Question]:
        return [q for q in self.questions if q.step == step]

    def in_group(self, group_id: str) -> list[Question]:
        return [q for q in self.questions if q.group == group_id]


def load_questions(path: Path = QUESTIONS_FILE) -> QuestionSet:
    with path.open(encoding="utf-8") as fh:
        return QuestionSet.model_validate(yaml.safe_load(fh))


@lru_cache(maxsize=1)
def question_set() -> QuestionSet:
    """The question file, read once per process."""
    return load_questions()


def agent_questions() -> list[Question]:
    """The dashboard agent's questions (step 2), in file order."""
    return question_set().step(2)


def main() -> None:
    """Print the question file as JSON (`make api-client` writes it to
    apps/web/src/mocks/questions.json for the mock API)."""
    import json
    import sys

    json.dump(question_set().model_dump(mode="json"), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
