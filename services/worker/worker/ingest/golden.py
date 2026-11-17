"""Golden plans against a candidate rule tree (validator (f) and E3's `run_golden` tool).

Each program's plans live in `data/golden/<program>/`; a must-pass plan must verify with an
accepted certificate, a must-fail plan must report its expected issue codes. The candidate
replaces that program's seed version; everything else comes from the seed bundle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from api.seed.bundle import SeedBundle, build_catalog, build_rules
from api.seed.models import GoldenPlan
from planner_core import check_certificate, verify
from planner_core.models import Catalog, ProgramRules, VerifyOptions


@dataclass
class GoldenOutcome:
    program_id: str
    total: int = 0
    passed: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.total > 0 and self.passed == self.total

    @property
    def skipped(self) -> bool:
        return self.total == 0

    def summary(self) -> str:
        if self.skipped:
            return f"no golden plans for {self.program_id}"
        text = f"{self.passed}/{self.total} golden plans behave as expected"
        return text + ("" if self.ok else ": " + "; ".join(self.failures[:10]))


GoldenRunner = Callable[[ProgramRules], GoldenOutcome]


def load_golden(root: Path, program_id: str) -> list[tuple[str, GoldenPlan]]:
    folder = root / program_id
    if not folder.is_dir():
        return []
    return [
        (p.name, GoldenPlan.model_validate(yaml.safe_load(p.read_text())))
        for p in sorted(folder.glob("*.yaml"))
    ]


def golden_runner(bundle: SeedBundle, golden_root: Path) -> GoldenRunner:
    catalog: Catalog = build_catalog(bundle)
    cache: dict[str, list[tuple[str, GoldenPlan]]] = {}

    def run(candidate: ProgramRules) -> GoldenOutcome:
        if candidate.id not in cache:
            cache[candidate.id] = load_golden(golden_root, candidate.id)
        out = GoldenOutcome(candidate.id)
        known = {p.id for p in bundle.programs} | {candidate.id}
        for name, golden in cache[candidate.id]:
            out.total += 1
            ids = [p.program_id for p in golden.plan.programs if p.program_id in known]
            rules = build_rules(bundle, ids)
            rules = rules.model_copy(
                update={
                    "programs": [p for p in rules.programs if p.id != candidate.id]
                    + [candidate.model_copy(update={"catalog_year": rules.catalog_year})]
                }
            )
            try:
                report = verify(golden.plan, rules, catalog, VerifyOptions(checks=golden.checks))
            except Exception as exc:  # a broken candidate must not stop the run
                out.failures.append(f"{name}: verifier error {type(exc).__name__}: {exc}")
                continue
            if golden.expect == "pass":
                errors = sorted({i.code for i in report.issues if i.level == "error"})
                accepted = report.certificate is not None and check_certificate(
                    golden.plan, rules, catalog, report.certificate
                )
                if errors or not accepted:
                    out.failures.append(f"{name}: expected pass, got errors {errors}")
                    continue
            else:
                found = {i.code for i in report.issues}
                missing = sorted(set(golden.expected_codes) - found)
                if missing:
                    out.failures.append(f"{name}: expected {missing}")
                    continue
            out.passed += 1
        return out

    return run
