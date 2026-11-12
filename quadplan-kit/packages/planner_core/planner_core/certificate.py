"""The trusted certificate checker. Implemented in prompt 02: linear time, no solver import,
under about 300 lines, readable line by line."""

from __future__ import annotations

from planner_core.models import Catalog, Certificate, PlanState, RuleSet


def check_certificate(
    plan: PlanState,
    rules: RuleSet,
    catalog: Catalog,
    certificate: Certificate,
) -> bool:
    """True only if every claim in `certificate` holds for `plan` under `rules` (SPEC
    "Certificates and the trusted checker"). `catalog` supplies course facts for selectors."""
    raise NotImplementedError("planner_core.check_certificate is built in prompt 02")
