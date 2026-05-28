# cron-scheduler-lite

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A minimal in-process job scheduler: interval-based jobs with run budgets, failure isolation, lateness measurement, and full run history — cron semantics without the daemon.

## 🚀 Overview

Background tasks shouldn't need a separate process to be reliable. `cron-scheduler-lite` runs periodic jobs in-process: register by `Job` object or a decorator (`@scheduler.every(30)`), drive it manually with `run_pending()` (perfect for tests) or let `run_forever()` poll. A failing job records its error and keeps the schedule alive — one crash never kills the loop. `max_runs` bounds finite jobs; every execution lands in history with duration and **lateness** (how late did it actually start?).

## ✨ Features

- **Interval jobs:** any callable, any interval; decorator or explicit registration
- **Run budgets:** `max_runs` exhausts a job cleanly (no more scheduling)
- **Failure isolation:** exceptions captured into the run record; scheduler continues
- **Lateness tracking:** scheduled vs actual start time on every record
- **Manual driving:** `run_pending()` for deterministic tests; `run_forever()` for production
- **History & summary:** per-job run counts, failures, exhaustion state
- **Injectable clock & sleep:** fully deterministic time behavior under test
- **Zero dependencies**

## 🚧 Structure

```
cron-scheduler-lite/
├── src/cron_lite/
│   ├── __init__.py
│   └── core.py
├── tests/
│   └── test_core.py
├── README.md
└── pyproject.toml
```

## 📦 Installation

```bash
git clone https://github.com/supremeloki/cron-scheduler-lite.git
cd cron-scheduler-lite
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## 📋 Requirements

- Python 3.11+
- No runtime dependencies

## 🏃 Quick Start

```python
from cron_lite import CronScheduler

scheduler = CronScheduler()

@scheduler.every(interval_seconds=60, max_runs=10)
def refresh_index():
    ...

scheduler.run_pending()      # execute whatever is due now
print(scheduler.summary())

scheduler.run_forever(poll_interval=5)   # production loop
```

## 🔧 Error Handling

```text
SchedulerError          # duplicate registration / invalid max_runs
JobNotFoundError        # lookup of unknown job id
InvalidIntervalError    # interval <= 0
```

Job-level exceptions never escape — they become data on the JobRun record.

## 🧪 Testing

```bash
pytest tests/ -v
```

## 📝 Code Quality

- Full type hints (`X | None` style), frozen run records
- Zero comments — names carry the meaning
- Due-time boundaries, exhaustion, failure recovery, and lateness covered against a fake clock

## 📄 License

MIT — see [LICENSE](LICENSE).

## 👤 Author

**Kooroush Masoumi** - [kooroushmasoumi@gmail.com](mailto:kooroushmasoumi@gmail.com)

---

⭐ Star this repo if you find it useful!
