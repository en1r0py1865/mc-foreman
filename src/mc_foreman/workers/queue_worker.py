from __future__ import annotations

import logging
from typing import Optional

from mc_foreman.domain.errors import ServiceException
from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.runtime.completion_notifier import CompletionNotifier

log = logging.getLogger("queue_worker")


class QueueWorker:
    def __init__(
        self,
        task_service,
        bridge: ExecutionBridge,
        completion_notifier: Optional[CompletionNotifier] = None,
    ):
        self.task_service = task_service
        self.bridge = bridge
        self.completion_notifier = completion_notifier

    def _safe_notify(self, task, *, result_ref=None, reason=None):
        """Deliver completion notification; never let delivery errors fail the task."""
        if self.completion_notifier is None:
            return
        try:
            self.completion_notifier.notify(task, result_ref=result_ref, reason=reason)
        except Exception as exc:
            log.error("delivery notification failed (task=%s): %s", task.task_id, exc, exc_info=True)

    def tick(self):
        task = self.task_service.dequeue_next()
        if task is None:
            return None
        try:
            result = self.bridge.execute(task)
            if result.success:
                completed = self.task_service.complete_task(task.task_id, result_ref=result.result_ref)
                self._safe_notify(completed, result_ref=result.result_ref)
                return completed
            reason = result.reason or "execution_failed"
            failed = self.task_service.fail_task(task.task_id, reason=reason)
            self._safe_notify(failed, reason=reason)
            return failed
        except ServiceException:
            raise
        except Exception as exc:
            reason = str(exc)
            failed = self.task_service.fail_task(task.task_id, reason=reason)
            self._safe_notify(failed, reason=reason)
            return failed
