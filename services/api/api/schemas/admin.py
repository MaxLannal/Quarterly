import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewNode(BaseModel):
    """One node of a proposed rule tree, with the quote it came from (prompt 09)."""

    path: str
    kind: str
    label: str | None = None
    summary: str
    quote: str | None = None
    url: str | None = None
    snapshot_id: str | None = None
    #: Why a person should look at this node (the second run disagrees, it changed since last
    #: year, the back-translation judge found a difference, the quote was not found).
    flags: list[str] = Field(default_factory=list)


class ReviewCheck(BaseModel):
    """One of the ingestion validators (a)-(g)."""

    id: str
    name: str
    ok: bool
    skipped: bool = False
    problems: list[str] = Field(default_factory=list)


class ReviewItemOut(BaseModel):
    id: int
    target_type: str
    target_id: str
    diff: dict[str, Any]
    reason: str | None = None
    status: Literal["open", "accepted", "rejected"]
    decided_at: dt.date | None = None
    #: A short title for the queue ("cmsc-bs 2027-28", "CMSC courses 2027-28").
    title: str = ""
    #: For program-version items: the version a curator publishes, and its status.
    program_version_id: int | None = None
    program_version_status: Literal["draft", "review", "published"] | None = None
    #: `review` (look at the flags) or `carry_over` (unchanged since last year).
    decision_hint: str | None = None
    nodes: list[ReviewNode] = Field(default_factory=list)
    checks: list[ReviewCheck] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    decision: Literal["accept", "reject", "edit"]
    #: For `edit`: the corrected content. Program versions take `{"rules": <ProgramRules>}`,
    #: prerequisites `{"prereq": <Expr>}`.
    edited: dict[str, Any] | None = None
    note: str | None = Field(default=None, max_length=1000)


class ProgramVersionOut(BaseModel):
    id: int
    program_id: str
    catalog_year: str
    status: Literal["draft", "review", "published"]
    verified_by: str | None = None
    verified_at: dt.date | None = None
    checksum: str
