"""Entry point of the verifier. Implemented in prompt 02 (verifier-engineer)."""

from __future__ import annotations

from planner_core.models import Catalog, PlanState, Report, RuleSet, VerifyOptions


def verify(
    plan: PlanState,
    rules: RuleSet,
    catalog: Catalog,
    options: VerifyOptions | None = None,
) -> Report:
    """Pure function: run checks V01-V12 and, when there are no errors, build a Certificate.

    Contract: deterministic for equal inputs; never performs I/O; `Report.plan_hash` equals
    `planner_core.hashing.plan_hash(plan)`; `Report.status` is "errors" if any issue has level
    "error", else "warnings" if any warning, else "valid"."""
    raise NotImplementedError("planner_core.verify is built in prompt 02")
