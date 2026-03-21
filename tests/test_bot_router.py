from pathlib import Path

from mc_foreman.bot.context import BotContext
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
from mc_foreman.domain.errors import ServiceException
from mc_foreman.workers.queue_worker import QueueWorker


class MockConfig:
    execution_mode = "mock"


class MockBridge(ExecutionBridge):
    def __init__(self):
        super().__init__(MockConfig())


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "data" / "bot_router_test.sqlite3"
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
    router = BotRouter(handlers)
    ctx1 = BotContext(user_id="router1")
    ctx2 = BotContext(user_id="router2")

    build1 = router.dispatch('/build 石头 喷泉 --size small', ctx1)
    build2 = router.dispatch('/build 日式 凉亭 --size medium --style japanese', ctx2)
    assert build1["data"]["state"] == "queued"
    assert build2["data"]["state"] == "queued"

    queue = router.dispatch('/queue', ctx2)
    assert queue["data"]["queue_length"] == 2
    assert queue["data"]["own_position"] == 2

    mybuilds = router.dispatch('/mybuilds', ctx1)
    assert len(mybuilds["data"]["items"]) == 1
    assert mybuilds["data"]["items"][0]["theme"] == '石头 喷泉'

    status_before = router.dispatch('/status', ctx1)
    task_id = status_before["data"]["task_id"]
    cancelled = router.dispatch(f'/cancel {task_id}', ctx1)
    assert cancelled["data"]["state"] == 'cancelled'

    completed = worker.tick()
    assert completed is not None
    assert completed.state == 'completed'

    help_data = router.dispatch('/help', ctx1)
    assert help_data["command"] == '/help'

    quoted = router.dispatch('/build "日式 花园" --size medium', BotContext(user_id="router3"))
    assert quoted["data"]["state"] == "queued"

    try:
        router.dispatch('/build "没关的引号', ctx1)
        raise AssertionError('expected invalid quoted command to fail')
    except ServiceException as exc:
        assert exc.code == 'INVALID_ARGUMENT'

    for bad_command in ['', '   ', '/unknown', '/build 喷泉 --size', '/cancel', '/status foo']:
        try:
            router.dispatch(bad_command, ctx1)
            raise AssertionError('expected invalid command to fail')
        except ServiceException:
            pass

    try:
        router.dispatch('/mybuilds --page 0', ctx1)
        raise AssertionError('expected invalid page to fail')
    except ServiceException as exc:
        assert exc.code == 'INVALID_ARGUMENT'

    print('bot router ok', build1["data"]["task_id"], build2["data"]["task_id"])

def test_main():
    main()


if __name__ == "__main__":
    main()
