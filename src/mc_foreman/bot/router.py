import shlex
from typing import List

from mc_foreman.domain.errors import ServiceException


class BotRouter:
    def __init__(self, handlers):
        self.handlers = handlers

    def dispatch(self, text: str, ctx) -> dict:
        parts = self._split(text)
        if not parts:
            raise ServiceException("INVALID_ARGUMENT", "空命令")

        command = parts[0]
        args = parts[1:]

        if command == "/build":
            return self._build(args, ctx)
        if command == "/status":
            return self._status(args, ctx)
        if command == "/mybuilds":
            return self._mybuilds(args, ctx)
        if command == "/queue":
            return self._queue(args, ctx)
        if command == "/help":
            return self.handlers["help"].handle()
        if command == "/cancel":
            return self._cancel(args, ctx)
        raise ServiceException("INVALID_ARGUMENT", f"未知命令：{command}")

    def _split(self, text: str) -> List[str]:
        stripped = text.strip()
        if not stripped:
            return []
        try:
            return shlex.split(stripped)
        except ValueError:
            raise ServiceException("INVALID_ARGUMENT", "参数有误：引号不完整")

    def _build(self, args, ctx):
        size = "small"
        style = None
        theme_parts = []
        idx = 0
        while idx < len(args):
            token = args[idx]
            if token == "--size":
                idx += 1
                if idx >= len(args):
                    raise ServiceException("INVALID_ARGUMENT", "参数有误：--size 缺少值")
                size = args[idx]
            elif token == "--style":
                idx += 1
                if idx >= len(args):
                    raise ServiceException("INVALID_ARGUMENT", "参数有误：--style 缺少值")
                style = args[idx]
            else:
                theme_parts.append(token)
            idx += 1
        theme = " ".join(theme_parts)
        return self.handlers["build"].handle(theme=theme, submitter_id=ctx.user_id, size=size, style=style)

    def _status(self, args, ctx):
        task_id = None
        if args:
            if len(args) == 2 and args[0] == "--task-id":
                task_id = args[1]
            else:
                raise ServiceException("INVALID_ARGUMENT", "参数有误：/status [--task-id <task_id>]")
        return self.handlers["status"].handle(submitter_id=ctx.user_id, task_id=task_id)

    def _mybuilds(self, args, ctx):
        page = 1
        if args:
            if len(args) == 2 and args[0] == "--page":
                page = int(args[1])
            else:
                raise ServiceException("INVALID_ARGUMENT", "参数有误：/mybuilds [--page <n>]")
        return self.handlers["mybuilds"].handle(submitter_id=ctx.user_id, page=page)

    def _queue(self, args, ctx):
        if args:
            raise ServiceException("INVALID_ARGUMENT", "参数有误：/queue")
        return self.handlers["queue"].handle(submitter_id=ctx.user_id)

    def _cancel(self, args, ctx):
        if len(args) != 1:
            raise ServiceException("INVALID_ARGUMENT", "参数有误：/cancel <task_id>")
        return self.handlers["cancel"].handle(task_id=args[0], submitter_id=ctx.user_id)
