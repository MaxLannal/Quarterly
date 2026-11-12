import asyncio

from worker.main import WorkerSettings, noop


def test_noop_job_returns_ok() -> None:
    assert asyncio.run(noop({})) == "ok"


def test_worker_registers_noop() -> None:
    assert noop in WorkerSettings.functions
    assert WorkerSettings.health_check_interval == 10
