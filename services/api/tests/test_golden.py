from pathlib import Path

import pytest
from api import golden
from api.cli import main as cli_main
from api_test_support import FIXTURES
from planner_core.hashing import plan_hash
from planner_core.models import Certificate, Issue, PlanState, Report, RuleSet

GOLDEN = FIXTURES / "golden"
SEED = FIXTURES / "seed"


def fake_verify(plan: PlanState, rules: RuleSet, *_: object) -> Report:
    terms = {i.course: i.term for i in plan.items}
    bad = terms.get("TEST 10100") == terms.get("TEST 10000")
    issues = [Issue(code="V03", level="error", message="prereq same term")] if bad else []
    cert = None if bad else Certificate(plan_hash=plan_hash(plan), rules={})
    return Report(
        status="errors" if bad else "valid",
        plan_hash=plan_hash(plan),
        core_version="x",
        issues=issues,
        certificate=cert,
    )


def test_runner_pass_and_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(golden, "verify", fake_verify)
    monkeypatch.setattr(golden, "check_certificate", lambda *a: True)
    lines: list[str] = []
    assert golden.run_golden(GOLDEN, SEED, lines.append) == 0
    assert any(line.startswith("PASS    test-bs/fail-01.yaml (fail)") for line in lines)
    assert any(line.startswith("PASS    test-bs/pass-01.yaml (pass)") for line in lines)
    monkeypatch.setattr(golden, "check_certificate", lambda *a: False)
    lines.clear()
    assert golden.run_golden(GOLDEN, SEED, lines.append) == 1
    assert any("certificate_accepted=False" in line for line in lines)


def test_runner_reports_missing_expected_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        golden, "verify", lambda p, *a: Report(status="valid", plan_hash="x", core_version="x")
    )
    lines: list[str] = []
    assert golden.run_golden(GOLDEN, SEED, lines.append) == 1
    assert any("missing ['V03']" in line for line in lines)


def test_runner_with_the_real_verifier() -> None:
    lines: list[str] = []
    assert golden.run_golden(GOLDEN, SEED, lines.append) == 0
    assert "PASS    test-bs/fail-01.yaml (fail)" in lines
    assert "PASS    test-bs/pass-01.yaml (pass)" in lines
    assert lines[-1] == "golden: PASS=2"


def test_runner_reports_skips_when_the_verifier_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def stub(*args: object) -> Report:
        raise NotImplementedError

    monkeypatch.setattr(golden, "verify", stub)
    lines: list[str] = []
    assert golden.run_golden(GOLDEN, SEED, lines.append) == 0
    assert lines[-1].startswith("golden: WARNING 2 plans not verified")


def test_runner_flags_invalid_files(tmp_path: Path) -> None:
    (tmp_path / "x.yaml").write_text(
        "id: x\ndescription: d\nprogram: test-bs\nexpect: fail\nplan: {catalog_year: '2099-00', entry_term: 2099-AU, programs: [{program_id: test-bs}]}\n"
    )
    (tmp_path / "y.yaml").write_text(
        "id: y\ndescription: d\nprogram: nope\nexpect: pass\nplan: {catalog_year: '2099-00', entry_term: 2099-AU, programs: [{program_id: nope}]}\n"
    )
    (tmp_path / "z.yaml").write_text(
        "id: z\ndescription: d\nprogram: test-bs\nexpect: pass\nplan: {catalog_year: '1999-00', entry_term: 2099-AU, programs: [{program_id: test-bs}]}\n"
    )
    lines: list[str] = []
    assert golden.run_golden(tmp_path, SEED, lines.append) == 1
    assert sum(line.startswith("INVALID") for line in lines) == 3


def test_no_golden_plans(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["golden", "--golden-dir", str(tmp_path / "none")]) == 0
    assert "no golden plans yet" in capsys.readouterr().out


def test_schema_export(tmp_path: Path) -> None:
    assert cli_main(["schemas", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "PlanState.json").exists() and (tmp_path / "golden.GoldenPlan.json").exists()
