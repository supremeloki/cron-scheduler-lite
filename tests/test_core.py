import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from cron_lite import (
    InvalidIntervalError,
    Job,
    JobNotFoundError,
    CronScheduler,
    SchedulerError,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


def test_job_interval_validation():
    with pytest.raises(InvalidIntervalError):
        Job(job_id="x", action=lambda: None, interval_seconds=0)
    with pytest.raises(SchedulerError):
        Job(job_id="x", action=lambda: None, interval_seconds=5, max_runs=0)


def test_register_and_list(clock):
    scheduler = CronScheduler(clock=clock)
    scheduler.register(Job(job_id="tick", action=lambda: None,
                           interval_seconds=10))
    assert scheduler.job_ids == ("tick",)


def test_duplicate_registration_rejected(clock):
    scheduler = CronScheduler(clock=clock)
    scheduler.register(Job(job_id="dup", action=lambda: None, interval_seconds=1))
    with pytest.raises(SchedulerError):
        scheduler.register(Job(job_id="dup", action=lambda: None, interval_seconds=2))


def test_run_pending_executes_due_jobs(clock):
    scheduler = CronScheduler(clock=clock)
    counter = {"n": 0}
    scheduler.register(Job(job_id="count", action=lambda: counter.__setitem__(
        "n", counter["n"] + 1), interval_seconds=5))
    clock.advance(5)
    scheduler.run_pending()
    assert counter["n"] == 1
    clock.advance(4)
    scheduler.run_pending()
    assert counter["n"] == 1
    clock.advance(1)
    scheduler.run_pending()
    assert counter["n"] == 2


def test_max_runs_exhaustion(clock):
    scheduler = CronScheduler(clock=clock)
    counter = {"n": 0}
    scheduler.register(Job(job_id="once", action=lambda: counter.__setitem__(
        "n", counter["n"] + 1), interval_seconds=1, max_runs=2))
    for _ in range(6):
        clock.advance(1)
        scheduler.run_pending()
    assert counter["n"] == 2
    job = scheduler.get_job("once")
    assert job.is_exhausted


def test_failed_job_records_error(clock):
    def explode() -> None:
        raise ValueError("boom")

    scheduler = CronScheduler(clock=clock)
    scheduler.register(Job(job_id="bomber", action=explode, interval_seconds=2))
    clock.advance(2)
    records = scheduler.run_pending()
    assert not records[0].success
    assert "boom" in records[0].error_summary
    job = scheduler.get_job("bomber")
    assert "boom" in (job.last_error or "")


def test_scheduler_continues_after_failure(clock):
    calls = {"ok": 0}

    def flaky() -> None:
        if calls["ok"] == 0 and not hasattr(flaky, "_failed"):
            flaky._failed = True
            raise RuntimeError("first time fails")
        calls["ok"] += 1

    scheduler = CronScheduler(clock=clock)
    scheduler.register(Job(job_id="flaky", action=flaky, interval_seconds=1))
    clock.advance(1)
    scheduler.run_pending()
    clock.advance(1)
    scheduler.run_pending()
    assert calls["ok"] == 1


def test_unregister_stops_execution(clock):
    scheduler = CronScheduler(clock=clock)
    counter = {"n": 0}
    scheduler.register(Job(job_id="temp", action=lambda: counter.__setitem__(
        "n", counter["n"] + 1), interval_seconds=1))
    assert scheduler.unregister("temp") is True
    clock.advance(10)
