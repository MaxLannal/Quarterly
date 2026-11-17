"""`make ingest-pilot` (the free `--fake` mode end to end, and the refusals of the paid mode)
and the cron jobs being off by default."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from worker.ingest import pilot
from worker.ingest.jobs import catalog_annual, catalog_monthly, cron_jobs, next_year
from worker.ingest.settings import IngestSettings, get_ingest_settings
from worker.main import WorkerSettings


def test_fake_pilot_reports_full_agreement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "report.md"
    assert pilot.main(["--fake", "--programs", "cmsc-ba,core", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "(no API calls)" in printed
    assert "node-level agreement 26/26 = 100.0%" in printed
    report = out.read_text()
    assert "# Pilot ingestion report (fake)" in report
    assert "FakeLLM scripted from the hand seed" in report
    assert "**26/26 = 100.0%** (target 95%: met)" in report
    assert "| cmsc-ba | 12 | 12 | 100.0% | 100.0% | none | 0 |" in report
    assert "## Every disagreement with the hand seed\n\nNone." in report
    assert "E2 enumeration: 2/2 pilot programs found; reconciliation passed" in report


def test_live_pages_fetch_the_seeds_http_pages_over_https(
    monkeypatch: pytest.MonkeyPatch, clock: Any
) -> None:
    """The seed cites catalog pages as http://; the paid pilot must still get every page,
    over https (spec review of 57c6723). No network: a mock transport answers."""
    import httpx
    from worker.ingest.snapshots import memory_archive

    bundle = pilot.load_bundle(pilot.ROOT / "data" / "seed" / "2026-27")
    programs = [p for p in bundle.programs if p.id in ("econ-ba", "core")]
    cited = {s.url for p in programs for s in p.sources if s.url}
    assert cited and all(u.startswith("http://") for u in cited)  # how the seed writes them
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, html="<html><body><p>page</p></body></html>")

    monkeypatch.setenv("CATALOG_CONTACT_EMAIL", "catalog-bot-test@example.edu")
    get_ingest_settings.cache_clear()
    try:
        pages = pilot.live_pages(
            programs,
            memory_archive("t"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            clock=clock.time,
            sleep=clock.sleep,
        )
    finally:
        get_ingest_settings.cache_clear()
    wanted = {u for p in programs for u in pilot.program_urls(p)}
    assert set(pages) == wanted and len(wanted) >= len(cited)
    assert all(u.startswith("https://") for u in asked)
    assert all(snap.url.startswith("https://") for snap in pages.values())


def test_the_report_lists_every_disagreement() -> None:
    bundle = pilot.load_bundle(pilot.ROOT / "data" / "seed" / pilot.YEAR)
    programs = [p for p in bundle.programs if p.id == "econ-ba"]
    report = pilot.PilotReport(mode="fake", catalog_year=pilot.YEAR)
    seed = programs[0].rules_only()
    data = seed.model_dump(mode="json", by_alias=True)
    data["rules"]["children"].pop()
    worse = pilot.ProgramRules.model_validate(data)
    agreement = pilot.node_agreement(seed, worse)
    report.programs.append(pilot.ProgramReport("econ-ba", pilot.count_nodes(seed), agreement, None))
    text = pilot.render(report)
    assert "NOT met" in text
    for d in agreement.disagreements:
        assert f"`{d.path}` | missing" in text


def test_the_paid_pilot_refuses_without_both_switches(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_gateway(**_: object) -> None:
        raise AssertionError("the gateway must not be built")

    monkeypatch.setattr("llm_gateway.gateway.build_gateway", no_gateway)
    monkeypatch.delenv("CONFIRM_SPEND", raising=False)
    monkeypatch.setenv("LLM_LIVE", "true")
    get_ingest_settings.cache_clear()
    try:
        assert pilot.main([]) == 2
        monkeypatch.setenv("CONFIRM_SPEND", "yes")
        monkeypatch.setenv("LLM_LIVE", "false")
        get_ingest_settings.cache_clear()
        assert pilot.main([]) == 2
    finally:
        get_ingest_settings.cache_clear()
    captured = capsys.readouterr()
    assert "estimated cost about $" in captured.out
    assert "CONFIRM_SPEND=yes LLM_LIVE=true make ingest-pilot" in captured.err


def test_estimate_uses_the_routing_prices() -> None:
    assert pilot.estimate(0, 0) > 0  # E2 alone costs something
    assert pilot.estimate(11, 86) > pilot.estimate(1, 86) > pilot.estimate(1, 0)
    assert pilot.main(["--estimate"]) == 0


def test_unknown_pilot_program() -> None:
    assert pilot.main(["--fake", "--programs", "nope"]) == 2


# ------------------------------------------------------------------------------ jobs


def test_cron_jobs_are_off_unless_enabled() -> None:
    assert cron_jobs(IngestSettings(_env_file=None)) == []  # type: ignore[call-arg]
    jobs = cron_jobs(IngestSettings(_env_file=None, catalog_ingest_enabled=True))  # type: ignore[call-arg]
    assert [j.name for j in jobs] == ["cron:catalog_annual", "cron:catalog_monthly"]
    assert (
        catalog_annual in WorkerSettings.functions and catalog_monthly in WorkerSettings.functions
    )


def test_jobs_do_nothing_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOG_INGEST_ENABLED", "false")
    get_ingest_settings.cache_clear()
    try:
        assert asyncio.run(catalog_annual({})).startswith("disabled")
        assert asyncio.run(catalog_monthly({})).startswith("disabled")
    finally:
        get_ingest_settings.cache_clear()


def test_next_year() -> None:
    assert next_year("2026-27") == "2027-28"
    assert next_year("2099-00") == "2100-01"
