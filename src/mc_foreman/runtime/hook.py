"""Runtime hook for intercepting mc_foreman slash commands.

Called from the agent/session runtime with a message text and user context.
Returns either a reply payload (command was handled) or a no-op indication
(message is not a mc_foreman command and should pass through).
"""
from mc_foreman.runtime.gateway import RuntimeGateway


class InterceptResult:
    """Result of attempting to intercept a message."""

    __slots__ = ("intercepted", "reply", "attachments", "bot_result", "reason")

    def __init__(self, intercepted, reply=None, attachments=None, bot_result=None, reason=None):
        # type: (bool, str, list, dict, str) -> None
        self.intercepted = intercepted
        self.reply = reply
        self.attachments = attachments or []
        self.bot_result = bot_result
        self.reason = reason

    def to_dict(self):
        # type: () -> dict
        d = {"intercepted": self.intercepted}
        if self.intercepted:
            d["reply"] = self.reply
            d["attachments"] = self.attachments
            d["bot_result"] = self.bot_result
        else:
            d["reason"] = self.reason
        return d


class RuntimeHook:
    def __init__(self, gateway):
        # type: (RuntimeGateway) -> None
        self._gateway = gateway

    def intercept(self, text, user_id, channel="default", chat_type="direct"):
        # type: (str, str, str, str) -> InterceptResult
        message = {
            "text": text,
            "user_id": user_id,
            "channel": channel,
            "chat_type": chat_type,
        }

        gw_result = self._gateway.handle(message)

        if gw_result["handled"]:
            return InterceptResult(
                intercepted=True,
                reply=gw_result["reply_text"],
                attachments=gw_result.get("attachments", []),
                bot_result=gw_result["bot_result"],
            )

        return InterceptResult(
            intercepted=False,
            reason=gw_result.get("reason", "not_mc_foreman_command"),
        )
