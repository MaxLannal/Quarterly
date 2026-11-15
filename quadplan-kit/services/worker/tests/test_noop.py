import asyncio

from worker.main import WorkerSettings, noop


def test_noop_job_returns_ok() -> None:
    assert asyncio.run(noop({})) == "ok"


def test_worker_registers_noop() -> None:
    assert noop in WorkerSettings.functions
    assert WorkerSettings.health_check_interval == 10


def test_worker_registers_the_spend_alarm_every_hour() -> None:
    from worker.main import WorkerSettings, hourly_spend_check

    assert hourly_spend_check in WorkerSettings.functions
    assert any(
        job.coroutine is hourly_spend_check and job.minute == 5 for job in WorkerSettings.cron_jobs
    )
