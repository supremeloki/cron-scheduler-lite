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
