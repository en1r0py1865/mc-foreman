from typing import Optional

from mc_foreman.domain.errors import ServiceException


class BuildHandler:
    def __init__(self, task_service, *, execution_mode: str = ""):
        self.task_service = task_service
        self._execution_mode = execution_mode

    def handle(self, *, theme: str, submitter_id: str, size: str = "small", style: Optional[str] = None) -> dict:
        if not theme or len(theme.strip()) == 0:
            raise ServiceException("INVALID_ARGUMENT", "参数有误：theme 不能为空")
        if size not in {"small", "medium"}:
            raise ServiceException("INVALID_ARGUMENT", "当前仅支持 small/medium")
        task = self.task_service.submit_task(theme=theme, submitter_id=submitter_id, size=size, style=style)
        return {
            "ok": True,
            "command": "/build",
            "data": {
                "task_id": task.task_id,
                "state": task.state,
                "execution_mode": self._execution_mode,
            },
            "error": None,
        }
