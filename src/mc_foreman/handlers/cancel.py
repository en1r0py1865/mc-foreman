from mc_foreman.domain.errors import ServiceException


class CancelHandler:
    def __init__(self, task_service):
        self.task_service = task_service

    def handle(self, *, task_id: str, submitter_id: str) -> dict:
        if not task_id or len(task_id.strip()) == 0:
            raise ServiceException("INVALID_ARGUMENT", "参数有误：task_id 不能为空")
        task = self.task_service.cancel_task(task_id=task_id, actor_id=submitter_id)
        return {
            "ok": True,
            "command": "/cancel",
            "data": {
                "task_id": task.task_id,
                "state": task.state,
            },
            "error": None,
        }
