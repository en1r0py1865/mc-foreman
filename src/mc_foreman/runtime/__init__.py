from mc_foreman.runtime.completion_notifier import CompletionDelivery, CompletionNotifier
from mc_foreman.runtime.gateway import RuntimeGateway
from mc_foreman.runtime.hook import InterceptResult, RuntimeHook
from mc_foreman.runtime.session_integration import handle_current_session_message


def bootstrap_runtime_hook(*args, **kwargs):
    from mc_foreman.runtime.bootstrap import bootstrap_runtime_hook as _bootstrap_runtime_hook

    return _bootstrap_runtime_hook(*args, **kwargs)


def bootstrap_worker(*args, **kwargs):
    from mc_foreman.runtime.bootstrap import bootstrap_worker as _bootstrap_worker

    return _bootstrap_worker(*args, **kwargs)


__all__ = [
    "RuntimeGateway",
    "RuntimeHook",
    "InterceptResult",
    "CompletionNotifier",
    "CompletionDelivery",
    "bootstrap_runtime_hook",
    "bootstrap_worker",
    "handle_current_session_message",
]
