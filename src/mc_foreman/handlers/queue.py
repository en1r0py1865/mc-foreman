class QueueHandler:
    def __init__(self, task_service):
        self.task_service = task_service

    def handle(self, *, submitter_id=None, limit: int = 5) -> dict:
        data = self.task_service.get_queue_summary(submitter_id=submitter_id, limit=limit)
        return {
            "ok": True,
            "command": "/queue",
            "data": data,
            "error": None,
        }
