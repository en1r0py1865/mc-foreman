"""Built-in minimal channel adapter for the runtime gateway (CORE).

Provides the simplest possible ``handle_message(dict) -> dict`` implementation
that routes messages through BotEntry and formats replies. Platform-specific
adapters live in the host layer and can replace this via
``bootstrap_runtime_hook(adapter_factory=...)``.
"""
from __future__ import annotations

class SimpleChannelAdapter:
    """Minimal channel adapter: routes messages through BotEntry, returns reply dict."""

    def __init__(self, bot_entry):
        self.bot_entry = bot_entry

    def handle_message(self, message):
        # type: (dict) -> dict
        text = (message.get("text") or "").strip()
        user_id = message.get("user_id") or ""
        channel = message.get("channel") or "default"
        chat_type = message.get("chat_type") or "direct"

        bot_result = self.bot_entry.handle_message(text=text, user_id=user_id)
        reply_text = self._format_reply(bot_result)

        return {
            "channel": channel,
            "chat_type": chat_type,
            "reply_text": reply_text,
            "attachments": [],
            "bot_result": bot_result,
        }

    @staticmethod
    def _format_reply(bot_result: dict) -> str:
        if not bot_result.get("ok"):
            error = bot_result.get("error") or {}
            return error.get("message", "系统暂时不可用")

        command = bot_result.get("command")
        data = bot_result.get("data") or {}

        if command == "/build":
            return "任务已提交 ✅\n任务ID: %s\n状态: %s" % (
                data.get("task_id", "?"), data.get("state", "?"))
        if command == "/status":
            return "状态: %s\n主题: %s" % (
                data.get("state", "?"), data.get("theme", ""))
        if command == "/help":
            cmds = data.get("commands") or []
            return "可用命令：" + " ".join(c.get("name", "") for c in cmds)
        if command == "/mybuilds":
            items = data.get("items") or []
            if not items:
                return "暂无构建记录"
            return "\n".join(
                "• %s %s %s" % (i.get("task_id", "?")[:8], i.get("state", "?"), i.get("theme", ""))
                for i in items
            )
        if command == "/queue":
            return "当前队列长度: %s" % data.get("queue_length", 0)
        if command == "/cancel":
            return "任务已取消"
        return str(data)
