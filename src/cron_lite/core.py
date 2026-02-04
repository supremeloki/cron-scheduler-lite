from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum


class SchedulerError(Exception):
    pass
