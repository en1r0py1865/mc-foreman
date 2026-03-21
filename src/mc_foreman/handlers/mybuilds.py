from mc_foreman.domain.errors import ServiceException


class MyBuildsHandler:
    def __init__(self, task_service, task_repo):
        self.task_service = task_service
        self.task_repo = task_repo

    def handle(self, *, submitter_id: str, page: int = 1, page_size: int = 5) -> dict:
        if page <= 0:
            raise ServiceException("INVALID_ARGUMENT", "参数有误：page 必须为正整数")
        tasks = self.task_repo.list_by_submitter(self.task_service.conn, submitter_id, page=page, page_size=page_size)
        items = [
            {
                "task_id": task.task_id,
                "state": task.state,
                "theme": task.theme,
                "created_at": task.created_at,
                "result_ref": task.result_ref,
            }
            for task in tasks
        ]
        return {
            "ok": True,
            "command": "/mybuilds",
            "data": {
                "items": items,
                "page": page,
            },
            "error": None,
        }
