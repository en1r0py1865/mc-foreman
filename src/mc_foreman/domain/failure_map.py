"""v1 failure reason classification — maps internal reason codes to user-facing text.

Internal codes are preserved in event logs / task metadata for debugging.
User-facing text is friendlier and avoids exposing raw internals.
"""

# Internal reason code → user-facing description (Chinese)
FAILURE_REASONS = {
    "claude_generation_failed": "AI 生成建筑命令时出错，请稍后重试",
    "command_extraction_failed": "无法从生成结果中提取有效命令",
    "rcon_send_failed": "向游戏服务器发送命令失败，请稍后重试",
    "zone_preload_failed": "建筑区域未能成功预加载，暂时无法确认实际施工",
    "command_verification_failed:no_place_commands": "生成的命令没有实际放置方块，已停止执行",
    "command_verification_failed:outside_zone": "生成的命令超出了分配施工区域，已停止执行",
    "build_verification_failed:no_block_change": "命令已发送，但没有观测到任何实际方块变化，因此不会标记完成",
    "delivery_failed": "结果推送失败，请使用 /status 查看",
    "execution_failed": "执行过程中出现错误",
}


def user_facing_reason(internal_reason):
    # type: (str | None) -> str
    """Return a user-friendly failure description for an internal reason code.

    Falls back to a generic message for unknown codes.
    """
    if not internal_reason:
        return "执行过程中出现未知错误"
    return FAILURE_REASONS.get(internal_reason, "执行过程中出现错误：%s" % internal_reason)


def is_known_failure(reason):
    # type: (str | None) -> bool
    """Check whether the reason code is a recognized v1 failure type."""
    return reason in FAILURE_REASONS
