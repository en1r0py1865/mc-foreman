from pathlib import Path

from mc_foreman.bot.entry import BotEntry
from mc_foreman.bot.router import BotRouter
from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.handlers.build import BuildHandler
from mc_foreman.handlers.cancel import CancelHandler
from mc_foreman.handlers.help import HelpHandler
from mc_foreman.handlers.mybuilds import MyBuildsHandler
from mc_foreman.handlers.queue import QueueHandler
from mc_foreman.handlers.status import StatusHandler
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.runtime.gateway import RuntimeGateway
from mc_foreman.services.task_service import TaskService
from mc_foreman.workers.queue_worker import QueueWorker


class MockConfig:
    execution_mode = "mock"
    execution_tmp_dir = Path(__file__).resolve().parents[1] / "data" / "runtime_gateway_exec"


class MockBridge(ExecutionBridge):
    def __init__(self):
        super().__init__(MockConfig())


def make_gateway():
    db_path = Path(__file__).resolve().parents[1] / "data" / "runtime_gateway_test.sqlite3"
    reset_db_files(db_path)
    conn = get_connection(db_path)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)
    worker = QueueWorker(task_service, MockBridge())

    handlers = {
        "build": BuildHandler(task_service),
        "status": StatusHandler(task_service, task_repo),
        "mybuilds": MyBuildsHandler(task_service, task_repo),
        "queue": QueueHandler(task_service),
        "help": HelpHandler(),
        "cancel": CancelHandler(task_service),
    }
    from mc_foreman.runtime.adapter import SimpleChannelAdapter
    adapter = SimpleChannelAdapter(BotEntry(BotRouter(handlers)))
    return RuntimeGateway(adapter), worker


def main():
    gateway, worker = make_gateway()

    assert gateway.should_handle({"text": "/help", "chat_type": "direct"}) is True
    assert gateway.should_handle({"text": "hello", "chat_type": "direct"}) is False
    assert gateway.should_handle({"text": "/help", "chat_type": "group"}) is False
    assert gateway.should_handle({"text": "/unknown", "chat_type": "direct"}) is False

    ignored = gateway.handle({
        "text": "hello there",
        "user_id": "ou_user1",
        "channel": "feishu",
        "chat_type": "direct",
    })
    assert ignored["handled"] is False

    help_reply = gateway.handle({
        "text": "/help",
        "user_id": "ou_user1",
        "channel": "feishu",
        "chat_type": "direct",
    })
    assert help_reply["handled"] is True
    assert "/build" in help_reply["reply_text"]

    build_reply = gateway.handle({
        "text": "/build 小喷泉 --size small",
        "user_id": "ou_user1",
        "channel": "feishu",
        "chat_type": "direct",
    })
    assert build_reply["handled"] is True
    assert "任务已提交" in build_reply["reply_text"]

    completed = worker.tick()
    assert completed is not None

    status_done = gateway.handle({
        "text": "/status",
        "user_id": "ou_user1",
        "channel": "feishu",
        "chat_type": "direct",
    })
    assert status_done["handled"] is True
    assert "image_paths" not in status_done

    bad_reply = gateway.handle({
        "text": "/build 小喷泉 --size",
        "user_id": "ou_user1",
        "channel": "feishu",
        "chat_type": "direct",
    })
    assert bad_reply["handled"] is True
    assert "参数有误" in bad_reply["reply_text"]
    assert isinstance(bad_reply.get("attachments", []), list)

    print("runtime gateway ok")

def test_main():
    main()


if __name__ == "__main__":
    main()
