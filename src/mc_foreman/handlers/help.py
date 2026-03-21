class HelpHandler:
    def handle(self) -> dict:
        return {
            "ok": True,
            "command": "/help",
            "data": {
                "commands": [
                    {"name": "/build", "usage": "/build <theme> [--size small|medium]", "desc": "提交建筑任务"},
                    {"name": "/status", "usage": "/status [--task-id <task_id>]", "desc": "查看当前或指定任务状态"},
                    {"name": "/mybuilds", "usage": "/mybuilds [--page 1]", "desc": "查看自己最近的建筑任务"},
                    {"name": "/cancel", "usage": "/cancel <task_id>", "desc": "取消自己仍在排队中的任务"},
                    {"name": "/queue", "usage": "/queue [--user <user_id>]", "desc": "查看公共队列摘要和自己的排位"},
                    {"name": "/help", "usage": "/help", "desc": "查看命令帮助"},
                ]
            },
            "error": None,
        }
