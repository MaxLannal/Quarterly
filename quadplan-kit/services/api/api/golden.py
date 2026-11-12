"""Golden-plan runner (`make golden`): verify every plan in data/golden against data/seed."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from planner_core import check_certificate, verify
from planner_core.models import VerifyOptions
from pydantic import ValidationError

from api.seed.bundle import SeedBundle, SeedError, build_catalog, build_rules, discover, load_bundle
from api.seed.models import GoldenPlan


def _load_golden(path: Path) -> GoldenPlan:
    import yaml

    return GoldenPlan.model_validate(yaml.safe_load(path.read_text()))


def _problems(golden: GoldenPlan, bundle: SeedBundle) -> list[str]:
    codes = {c.code for c in bundle.courses}
    programs = {p.id for p in bundle.programs}
    out = [
        f"unknown program {p.program_id}"
        for p in golden.plan.programs
        if p.program_id not in programs
    ]
    out += [
        f"unknown course {i.course}"
        for i in golden.plan.items
        if i.course and i.course not in codes
    ]
    return out


def run_golden(golden_root: Path, seed_root: Path, out: Callable[[str], None] = print) -> int:
    files = sorted(golden_root.rglob("*.yaml")) if golden_root.is_dir() else []
    if not files:
        out("golden: no golden plans yet")
        return 0
    bundles = {d.name: d for d in discover(seed_root)}
    loaded: dict[str, SeedBundle] = {}
    tally: Counter[str] = Counter()
    per_program: dict[str, Counter[str]] = {}
    for path in files:
        rel = path.relative_to(golden_root)
        try:
            golden = _load_golden(path)
            year = golden.plan.catalog_year
            if year not in bundles:
                raise SeedError(f"no seed for catalog year {year}")
            bundle = loaded.setdefault(year, load_bundle(bundles[year]))
            if problems := _problems(golden, bundle):
                raise SeedError("; ".join(problems))
        except (ValidationError, SeedError, OSError) as exc:
            out(f"INVALID {rel}: {exc}")
            tally["INVALID"] += 1
            continue
        rules = build_rules(bundle, [p.program_id for p in golden.plan.programs])
        catalog = build_catalog(bundle)
        verdict, detail = "PASS", ""
        try:
            report = verify(golden.plan, rules, catalog, VerifyOptions(checks=golden.checks))
        except NotImplementedError:
            verdict, detail = "SKIP", "planner_core.verify not implemented yet (prompt 02)"
        else:
            found = sorted({i.code for i in report.issues})
            if golden.expect == "pass":
                errors = sorted({i.code for i in report.issues if i.level == "error"})
                accepted = report.certificate is not None and check_certificate(
                    golden.plan, rules, catalog, report.certificate
                )
                if errors or not accepted:
                    verdict = "FAIL"
                    detail = f"expected pass; errors={errors} certificate_accepted={accepted}"
            else:
                missing = sorted(set(golden.expected_codes) - set(found))
                if missing:
                    verdict, detail = (
                        "FAIL",
                        f"expected {golden.expected_codes}, missing {missing}; got {found}",
                    )
        tally[verdict] += 1
        per_program.setdefault(golden.program, Counter())[f"{golden.expect}:{verdict}"] += 1
        out(f"{verdict:7} {rel} ({golden.expect})" + (f": {detail}" if detail else ""))
    for program, counts in sorted(per_program.items()):
        out(f"  {program}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    out("golden: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    if tally["SKIP"]:
        out(f"golden: WARNING {tally['SKIP']} plans not verified (verifier missing)")
    return 1 if tally["FAIL"] or tally["INVALID"] else 0
