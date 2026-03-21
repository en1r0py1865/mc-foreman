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
from mc_foreman.services.task_service import TaskService


class MockConfig:
    execution_mode = "mock"


class MockBridge(ExecutionBridge):
    def __init__(self):
        super().__init__(MockConfig())


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "data" / "bot_entry_test.sqlite3"
    reset_db_files(db_path)

    conn = get_connection(db_path)
    init_db(conn)
    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    handlers = {
        "build": BuildHandler(task_service),
        "status": StatusHandler(task_service, task_repo),
        "mybuilds": MyBuildsHandler(task_service, task_repo),
        "queue": QueueHandler(task_service),
        "help": HelpHandler(),
        "cancel": CancelHandler(task_service),
    }
    entry = BotEntry(BotRouter(handlers))

    ok = entry.handle_message(text='/build 小喷泉 --size small', user_id='entry1')
    assert ok["ok"] is True
    assert ok["command"] == "/build"

    bad = entry.handle_message(text='/build 小喷泉 --size', user_id='entry1')
    assert bad["ok"] is False
    assert bad["error"]["code"] == 'INVALID_ARGUMENT'
    assert '参数有误' in bad["error"]["message"]

    unknown = entry.handle_message(text='/unknown', user_id='entry1')
    assert unknown["ok"] is False
    assert unknown["error"]["code"] == 'INVALID_ARGUMENT'

    print('bot entry ok')

def test_main():
    main()


if __name__ == '__main__':
    main()
