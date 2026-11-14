"""The eval runner (evals/run.py) without spending anything: the free checks, the refusal
without CONFIRM_SPEND=yes, and one live pass of the plumbing on FakeLLM."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from llm_gateway.api import FakeLLM, ToolCall

RUN = Path(__file__).resolve().parents[3] / "evals" / "run.py"


def runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evals_run", RUN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["evals_run"] = module
    spec.loader.exec_module(module)
    return module


def test_offline_checks_pass_and_live_runs_need_consent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run = runner()
    assert run.main(["--offline"]) == 0
    monkeypatch.delenv("CONFIRM_SPEND", raising=False)
    assert run.main([]) == 2
    out = capsys.readouterr()
    assert "estimated cost" in out.out and "refusing" in out.err


class FakeGateway:
    """FakeLLM with the real gateway's `sink` keyword."""

    def __init__(self, fake: FakeLLM) -> None:
        self.fake = fake

    def structured(self, task: str, *, sink: Any = None, **kw: Any) -> Any:
        return self.fake.structured(task, **kw)

    def run_agent(self, spec: Any, *, sink: Any = None) -> Any:
        return self.fake.run_agent(spec, sink=sink)


@pytest.mark.db
def test_one_live_pass_on_a_fake_gateway(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = runner()
    answer = ToolCall("submit_answer", {"text": "Students found it useful.", "citations": []})
    fake = FakeLLM(
        script={
            "a2_scope_classifier": [{"label": "off_topic"}, {"label": "in_scope"}] * 2,
            "a2_advisor_chat": [answer, answer],
        }
    )
    import llm_gateway.gateway as gateway

    monkeypatch.setattr(gateway, "build_gateway", lambda **_: FakeGateway(fake))
    monkeypatch.setattr(run, "OUT", tmp_path)
    monkeypatch.setenv("CONFIRM_SPEND", "yes")
    status = run.main(["--only", "a2", "--limit", "1"])
    report = next(tmp_path.glob("report-*.json")).read_text()
    assert '"suite": "a2-off-topic"' in report and '"suite": "a2-injection"' in report
    # The in-scope case lacks its citation on this fake, so the run reports a failure.
    assert '"suite": "a2-in-scope"' in report and status == 1
