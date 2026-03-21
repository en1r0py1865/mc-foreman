ERROR_MESSAGES = {
    "INVALID_ARGUMENT": "参数有误：{detail}",
    "RATE_LIMITED": "你已有一个排队中的任务，请等待完成后再提交",
    "FORBIDDEN": "主题内容未通过审核",
    "NOT_FOUND": "找不到该任务",
    "CONFLICT": "该任务状态已变更，无法操作",
    "SYSTEM_UNAVAILABLE": "系统暂时不可用，请稍后重试",
}


def to_user_message(code: str, detail: str) -> str:
    template = ERROR_MESSAGES.get(code, ERROR_MESSAGES["SYSTEM_UNAVAILABLE"])
    if "{detail}" in template:
        normalized = detail
        prefix = "参数有误："
        if code == "INVALID_ARGUMENT" and normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
        return template.format(detail=normalized)
    return template
