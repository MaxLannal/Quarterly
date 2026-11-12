import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel


class ReviewItemOut(BaseModel):
    id: int
    target_type: str
    target_id: str
    diff: dict[str, Any]
    reason: str | None = None
    status: Literal["open", "accepted", "rejected"]
    decided_at: dt.date | None = None


class ReviewDecision(BaseModel):
    decision: Literal["accept", "reject", "edit"]
    edited: dict[str, Any] | None = None
    note: str | None = None


class ProgramVersionOut(BaseModel):
    id: int
    program_id: str
    catalog_year: str
    status: Literal["draft", "review", "published"]
    verified_by: str | None = None
    verified_at: dt.date | None = None
    checksum: str
