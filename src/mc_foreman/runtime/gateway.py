SUPPORTED_COMMANDS = {
    "/build",
    "/status",
    "/mybuilds",
    "/queue",
    "/help",
    "/cancel",
}


class RuntimeGateway:
    """Gateway that routes recognised /commands to a channel adapter.

    The *adapter* must implement ``handle_message(message: dict) -> dict``.
    Any platform adapter satisfying this protocol
    can be injected — no concrete import required.
    """

    def __init__(self, adapter):
        self.adapter = adapter

    def should_handle(self, message):
        # type: (dict) -> bool
        text = (message.get("text") or "").strip()
        chat_type = message.get("chat_type") or "direct"
        if not text.startswith("/"):
            return False
        if chat_type != "direct":
            return False
        command = text.split()[0]
        return command in SUPPORTED_COMMANDS

    def handle(self, message):
        # type: (dict) -> dict
        if not self.should_handle(message):
            return {"handled": False, "reply_text": None, "reason": "not_mc_foreman_command"}

        result = self.adapter.handle_message(message)
        return {
            "handled": True,
            "reply_text": result["reply_text"],
            "attachments": result.get("attachments", []),
            "channel": result["channel"],
            "chat_type": result["chat_type"],
            "bot_result": result["bot_result"],
        }
