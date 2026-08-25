from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum


class SchedulerError(Exception):
    pass


class JobNotFoundError(SchedulerError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"job not found: {job_id!r}")


class InvalidIntervalError(SchedulerError):
    pass


@dataclass(frozen=True)
class JobRun:
    job_id: str
    scheduled_at: float
    started_at: float
    finished_at: float
    success: bool
    error_summary: str | None = None

    @property
    def duration(self) -> float:
        return round(self.finished_at - self.started_at, 4)

    @property
    def lateness(self) -> float:
        return round(max(0.0, self.started_at - self.scheduled_at), 4)


@dataclass
class Job:
    job_id: str
    action: Callable[[], None]
    interval_seconds: float
    max_runs: int | None = None
    enabled: bool = True
    runs_completed: int = 0
    next_run_at: float = 0.0
    last_error: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise InvalidIntervalError("interval must be > 0")
        if self.max_runs is not None and self.max_runs < 1:
            raise SchedulerError("max_runs must be >= 1")

    @property
    def is_exhausted(self) -> bool:
        return self.max_runs is not None and self.runs_completed >= self.max_runs

    def is_due(self, at_time: float | None = None) -> bool:
        moment = at_time if at_time is not None else time.monotonic()
        return (self.enabled and not self.is_exhausted
                and moment >= self.next_run_at)

    def reschedule(self, now: float) -> float:
        self.next_run_at = now + self.interval_seconds
        return self.next_run_at


class CronScheduler:
    def __init__(self, clock: Callable[[], float] | None = None,
                 sleep: Callable[[float], None] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._jobs: dict[str, Job] = {}
        self._runs: list[JobRun] = []

    @property
    def now(self) -> float:
        return self._clock()

    def register(self, job: Job, *, start_immediately: bool = True) -> "CronScheduler":
        if job.job_id in self._jobs:
            raise SchedulerError(f"job already registered: {job.job_id!r}")
        job.next_run_at = self.now if start_immediately \
            else self.now + job.interval_seconds
        self._jobs[job.job_id] = job
        return self

    def every(self, interval_seconds: float, job_id: str | None = None,
              max_runs: int | None = None) -> Callable[[Callable[[], None]], Job]:
        def decorator(action: Callable[[], None]) -> Job:
            identifier = job_id or action.__name__
            job = Job(job_id=identifier, action=action,
                      interval_seconds=interval_seconds, max_runs=max_runs)
            self.register(job)
            return job
        return decorator

    def unregister(self, job_id: str) -> bool:
        removed = self._jobs.pop(job_id, None)
        return removed is not None

    def get_job(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    @property
    def job_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._jobs))

    def due_jobs(self) -> list[Job]:
        moment = self.now
        return [job for job in sorted(self._jobs.values(),
                                      key=lambda j: j.next_run_at)
                if job.is_due(moment)]

    def run_pending(self) -> list[JobRun]:
        executed: list[JobRun] = []
        for job in self.due_jobs():
            executed.append(self.execute(job))
        return executed

    def execute(self, job: Job) -> JobRun:
        scheduled = job.next_run_at
        started = self._clock()
        try:
            job.action()
            success, error = True, None
        except Exception as exc:
            success, error = False, f"{type(exc).__name__}: {exc}"
            job.last_error = error
        finished = self._clock()
        job.runs_completed += 1
        record = JobRun(
            job_id=job.job_id,
            scheduled_at=scheduled,
            started_at=started,
            finished_at=finished,
            success=success,
            error_summary=error,
        )
        self._runs.append(record)
        if not job.is_exhausted:
            job.reschedule(finished)
        return record

    def run_forever(self, poll_interval: float = 1.0,
                    stop_condition: Callable[[], bool] | None = None) -> None:
        while not (stop_condition and stop_condition()):
            pending = self.run_pending()
            if not pending:
                self._sleep(poll_interval)

    def run_history(self, job_id: str | None = None) -> tuple[JobRun, ...]:
        if job_id is None:
            return tuple(self._runs)
        return tuple(run for run in self._runs if run.job_id == job_id)

    def summary(self) -> dict[str, dict]:
        return {
            job_id: {
                "runs": len(self.run_history(job_id)),
                "failures": sum(1 for r in self.run_history(job_id) if not r.success),
                "enabled": job.enabled,
                "exhausted": job.is_exhausted,
                "next_run_at": job.next_run_at,
            }
            for job_id, job in sorted(self._jobs.items())
        }


def collect_results(scheduler: CronScheduler, cycles: int) -> Iterable[JobRun]:
    for _ in range(cycles):
        yield from scheduler.run_pending()
