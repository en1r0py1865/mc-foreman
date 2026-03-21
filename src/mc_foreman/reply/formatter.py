from mc_foreman.domain.errors import ServiceException
from mc_foreman.reply.error_map import to_user_message


def format_success(result: dict) -> dict:
    return result


def format_error(exc: Exception) -> dict:
    if isinstance(exc, ServiceException):
        return {
            "ok": False,
            "command": None,
            "data": None,
            "error": {
                "code": exc.code,
                "message": to_user_message(exc.code, exc.message),
            },
        }
    return {
        "ok": False,
        "command": None,
        "data": None,
        "error": {
            "code": "SYSTEM_UNAVAILABLE",
            "message": to_user_message("SYSTEM_UNAVAILABLE", ""),
        },
    }
