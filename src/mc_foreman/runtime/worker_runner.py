from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class WorkerRunSummary:
    processed: int
    completed_task_ids: List[str]
    failed_task_ids: List[str]


class WorkerRunner:
    """Minimal worker driver for v1 validation and local runtime use.

    Repeatedly calls ``worker.tick()`` until either:
    - queue becomes empty, or
    - a task was processed and ``run_until_empty`` is False, or
    - timeout is reached.
    """

    def __init__(self, worker):
        self.worker = worker

    def run(self, *, run_until_empty: bool = True, max_ticks: int = 20, sleep_seconds: float = 0.0, timeout_seconds: Optional[float] = None) -> WorkerRunSummary:
        started = time.time()
        processed = 0
        completed_task_ids: List[str] = []
        failed_task_ids: List[str] = []

        for _ in range(max_ticks):
            if timeout_seconds is not None and (time.time() - started) >= timeout_seconds:
                break

            item = self.worker.tick()
            if item is None:
                break

            processed += 1
            if item.state == "completed":
                completed_task_ids.append(item.task_id)
            elif item.state == "failed":
                failed_task_ids.append(item.task_id)

            if not run_until_empty:
                break

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        return WorkerRunSummary(
            processed=processed,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
        )
