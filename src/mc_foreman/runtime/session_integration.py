def handle_current_session_message(*, text, user_id, channel, chat_type, db_path=None):
    from mc_foreman.runtime.bootstrap import bootstrap_runtime_hook

    hook = bootstrap_runtime_hook(db_path=db_path)
    result = hook.intercept(text, user_id=user_id, channel=channel, chat_type=chat_type)
    payload = result.to_dict()
    if result.intercepted:
        return {
            "handled": True,
            "reply_text": payload.get("reply"),
            "attachments": payload.get("attachments", []),
            "bot_result": payload.get("bot_result"),
            "normalized_text": text,
        }
    return {
        "handled": False,
        "reason": payload.get("reason", "not_mc_foreman_command"),
        "reply_text": None,
        "attachments": [],
        "bot_result": None,
        "normalized_text": text,
    }
