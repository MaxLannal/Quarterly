"""JSON Schemas of the contracts, written to docs/schemas/ by `make api-client`."""

from __future__ import annotations

from typing import Any

from planner_core import models as pm
from pydantic import TypeAdapter

from api.seed.models import CourseListsFile, CoursesFile, GoldenPlan, ProgramSeed, TermsFile

EXPORTED: dict[str, Any] = {
    "Expr": pm.Expr,
    "Node": pm.Node,
    "Selector": pm.Selector,
    "ProgramRules": pm.ProgramRules,
    "CollegePolicy": pm.CollegePolicy,
    "Requisite": pm.Requisite,
    "RuleSet": pm.RuleSet,
    "Catalog": pm.Catalog,
    "PlanState": pm.PlanState,
    "Goal": pm.Goal,
    "VerifyOptions": pm.VerifyOptions,
    "Report": pm.Report,
    "Issue": pm.Issue,
    "Certificate": pm.Certificate,
    "ChangeOp": pm.ChangeOp,
    "ChangeSet": pm.ChangeSet,
    "seed.CoursesFile": CoursesFile,
    "seed.TermsFile": TermsFile,
    "seed.CourseListsFile": CourseListsFile,
    "seed.ProgramSeed": ProgramSeed,
    "golden.GoldenPlan": GoldenPlan,
}


def export() -> dict[str, dict[str, Any]]:
    return {name: TypeAdapter(tp).json_schema(by_alias=True) for name, tp in EXPORTED.items()}
