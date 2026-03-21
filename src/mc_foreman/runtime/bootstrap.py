"""Factory to wire up the full mc_foreman runtime stack (CORE).

Creates all repositories, services, handlers, router, adapter, gateway,
and hook in one call — no external dependencies required.

Host-specific wiring (external delivery and other host-only features) should
be done by the caller before passing dependencies into these functions.
"""
from pathlib import Path
from typing import Callable, Optional

from mc_foreman.bot.entry import BotEntry
from mc_foreman.bot.router import BotRouter
from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.handlers.build import BuildHandler
from mc_foreman.handlers.cancel import CancelHandler
from mc_foreman.handlers.help import HelpHandler
from mc_foreman.handlers.mybuilds import MyBuildsHandler
from mc_foreman.handlers.queue import QueueHandler
from mc_foreman.handlers.status import StatusHandler
from mc_foreman.infra.db import get_connection, init_db
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.runtime.channel_delivery import ChannelDeliveryCallback
from mc_foreman.runtime.completion_notifier import CompletionNotifier
from mc_foreman.runtime.gateway import RuntimeGateway
from mc_foreman.runtime.hook import RuntimeHook
from mc_foreman.services.task_service import TaskService
from mc_foreman.workers.queue_worker import QueueWorker


def _infer_project_root() -> Path:
    """Infer the project root from this file's location.

    Assumes the standard layout ``<root>/src/mc_foreman/runtime/bootstrap.py``.
    """
    return Path(__file__).resolve().parents[3]


def _default_adapter(bot_entry):
    """Build the default channel adapter (CORE built-in)."""
    from mc_foreman.runtime.adapter import SimpleChannelAdapter
    return SimpleChannelAdapter(bot_entry)


# Minimal cache: reuse RuntimeHook when db_path hasn't changed.
_hook_cache = {}  # {resolved_db_path_str: RuntimeHook}


def _resolve_db_path(db_path, project_root=None):
    """Resolve db_path to a canonical Path, applying default if None."""
    if db_path is None:
        root = project_root or _infer_project_root()
        db_path = root / "data" / "mc_foreman.sqlite3"
    return Path(db_path).resolve()


def reset_runtime_hook_cache():
    """Clear the bootstrap_runtime_hook cache.

    Call this in tests or when the db_path changes to force a fresh bootstrap.
    """
    _hook_cache.clear()


def bootstrap_runtime_hook(db_path=None, adapter_factory=None):
    # type: (Path, Optional[Callable]) -> RuntimeHook
    """Create a fully-wired RuntimeHook ready for use.

    Caches the result per resolved *db_path* so repeated calls with the same
    path reuse the existing hook stack instead of rebuilding it each time.

    Args:
        db_path: SQLite database path.  When *None*, uses the default
            ``data/mc_foreman.sqlite3`` relative to the project root.
        adapter_factory: Optional callable ``(BotEntry) -> adapter``.
            Defaults to building the reference ChannelAdapter.

    Returns:
        A :class:`RuntimeHook` instance connected to a live database.
    """
    resolved = _resolve_db_path(db_path)
    cache_key = str(resolved)

    if cache_key in _hook_cache:
        return _hook_cache[cache_key]

    resolved.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(resolved)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    handlers = {
        "build": BuildHandler(task_service),
        "status": StatusHandler(task_service, task_repo, event_repo=event_repo),
        "mybuilds": MyBuildsHandler(task_service, task_repo),
        "queue": QueueHandler(task_service),
        "help": HelpHandler(),
        "cancel": CancelHandler(task_service),
    }

    bot_entry = BotEntry(BotRouter(handlers))
    build_adapter = adapter_factory or _default_adapter
    adapter = build_adapter(bot_entry)
    gateway = RuntimeGateway(adapter)
    hook = RuntimeHook(gateway)

    _hook_cache[cache_key] = hook
    return hook


class _MockConfig:
    execution_mode = "mock"
    execution_tmp_dir = _infer_project_root() / "data" / "execution"


def bootstrap_worker(
    db_path=None,
    completion_notifier=None,
    deliver_fn=None,
    channel_delivery=None,
    channel_name="default",
    config=None,
):
    # type: (Optional[Path], Optional[CompletionNotifier], Optional[Callable], Optional[ChannelDeliveryCallback], str, object) -> tuple
    """Create a fully-wired QueueWorker ready for use (CORE).

    All dependencies are injected — no host-specific logic here.
    For external auto-delivery, construct the notifier in the host layer
    and pass it as *completion_notifier*.

    Args:
        db_path: SQLite database path.
        completion_notifier: Pre-built notifier (takes priority).
        deliver_fn: Simple callable for legacy / test usage.
        channel_delivery: Structured :class:`ChannelDeliveryCallback`.
        channel_name: Channel identifier passed to the callback envelope.
        config: Execution config (defaults to mock mode).

    Returns:
        Tuple of (QueueWorker, TaskService) — service exposed for testing.
    """
    if db_path is None:
        db_path = _infer_project_root() / "data" / "mc_foreman.sqlite3"

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    if config is None:
        config = _MockConfig()

    bridge = ExecutionBridge(config)

    notifier = completion_notifier
    if notifier is None:
        # channel_delivery (structured) takes precedence over raw deliver_fn
        if channel_delivery is not None:
            notifier = CompletionNotifier(
                deliver_fn=channel_delivery.as_deliver_fn(channel=channel_name),
            )
        elif deliver_fn is not None:
            notifier = CompletionNotifier(deliver_fn=deliver_fn)

    worker = QueueWorker(task_service, bridge, completion_notifier=notifier)
    return worker, task_service
