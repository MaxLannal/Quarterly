"""Canonical hashes: `plan_hash` keys cached reports and change sets; `rules_hash` pins the rule
versions a certificate was issued against."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel

from planner_core.models import PlanState, ProgramRules


def canonical_json(data: Any) -> str:
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json", by_alias=True)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_of(data: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(data).encode()).hexdigest()


def plan_hash(plan: PlanState) -> str:
    """Order-insensitive hash of everything that affects verification. Item ids are ignored."""
    data = plan.model_dump(mode="json", by_alias=True)
    for item in data["items"]:
        item.pop("id", None)
    for key in ("items", "credits", "programs", "goals"):
        data[key].sort(key=canonical_json)
    data["placements"].sort()
    return sha256_of(data)


def program_key(program: ProgramRules) -> str:
    """Certificate key for a program version: `<id>@<catalog year>`."""
    return f"{program.id}@{program.catalog_year}"


def rules_hash(program: ProgramRules) -> str:
    return sha256_of(program)
