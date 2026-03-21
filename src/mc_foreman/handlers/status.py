import json
from typing import Optional

from mc_foreman.artifacts.result_bundle import load_result_bundle
from mc_foreman.domain.errors import ServiceException
from mc_foreman.domain.failure_map import user_facing_reason


class StatusHandler:
    def __init__(self, task_service, task_repo, event_repo=None):
        self.task_service = task_service
        self.task_repo = task_repo
        self.event_repo = event_repo

    def _get_failure_reason(self, task_id):
        """Extract the internal failure reason from the fail event, if available."""
        if self.event_repo is None:
            return None
        events = self.event_repo.list_by_task(self.task_service.conn, task_id)
        for event in reversed(events):
            if event.new_state == "failed" and event.detail_json:
                try:
                    detail = json.loads(event.detail_json)
                    return detail.get("reason")
                except (json.JSONDecodeError, TypeError):
                    pass
        return None

    def handle(self, *, submitter_id: str, task_id: Optional[str] = None) -> dict:
        if task_id is None:
            tasks = self.task_repo.list_by_submitter(self.task_service.conn, submitter_id, page=1, page_size=1)
            if not tasks:
                raise ServiceException("NOT_FOUND", "当前没有可查看的任务")
            task = tasks[0]
        else:
            task = self.task_service.get_task(task_id)
            if task is None:
                raise ServiceException("NOT_FOUND", "找不到该任务")
            if task.submitter_id != submitter_id:
                raise ServiceException("FORBIDDEN", "无权查看该任务")

        manifest = load_result_bundle(task.result_ref) if task.result_ref else {}
        verification = manifest.get("verification", {}) if manifest else {}
        execution_mode = verification.get("mode") or ("mock" if str(task.result_ref or "").startswith("mock://") else None)

        data = {
            "task_id": task.task_id,
            "state": task.state,
            "theme": task.theme,
            "created_at": task.created_at,
            "result_ref": task.result_ref,
            "execution_mode": execution_mode,
            "verification": verification,
        }

        if task.state == "failed":
            internal_reason = self._get_failure_reason(task.task_id)
            data["failure_reason"] = user_facing_reason(internal_reason)
            data["failure_code"] = internal_reason

        return {
            "ok": True,
            "command": "/status",
            "data": data,
            "error": None,
        }
