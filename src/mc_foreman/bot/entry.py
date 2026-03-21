from mc_foreman.bot.context import BotContext
from mc_foreman.reply.formatter import format_error, format_success


class BotEntry:
    def __init__(self, router):
        self.router = router

    def handle_message(self, *, text: str, user_id: str) -> dict:
        try:
            result = self.router.dispatch(text, BotContext(user_id=user_id))
            return format_success(result)
        except Exception as exc:
            return format_error(exc)
