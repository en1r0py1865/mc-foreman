from pathlib import Path

from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.services.task_service import TaskService
from mc_foreman.handlers.mybuilds import MyBuildsHandler
from mc_foreman.handlers.queue import QueueHandler
from mc_foreman.handlers.help import HelpHandler


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "data" / "command_surface_test.sqlite3"
    reset_db_files(db_path)

    conn = get_connection(db_path)
    init_db(conn)
    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    t1 = task_service.submit_task(theme="喷泉", submitter_id="u1", size="small")
    t2 = task_service.submit_task(theme="凉亭", submitter_id="u2", size="medium")

    mybuilds = MyBuildsHandler(task_service, task_repo).handle(submitter_id="u1")
    assert mybuilds["data"]["items"][0]["task_id"] == t1.task_id
    assert mybuilds["data"]["items"][0]["theme"] == "喷泉"

    queue = QueueHandler(task_service).handle(submitter_id="u2")
    assert queue["data"]["queue_length"] == 2
    assert queue["data"]["own_task_id"] == t2.task_id
    assert queue["data"]["own_position"] == 2
    assert queue["data"]["items"][0]["public_summary"].startswith("一个小型")
    assert queue["data"]["items"][1]["public_summary"].startswith("一个中型")
    assert "submitter_id" not in queue["data"]["items"][0]
    assert "task_id" not in queue["data"]["items"][0]

    help_data = HelpHandler().handle()
    names = [item["name"] for item in help_data["data"]["commands"]]
    assert "/mybuilds" in names
    assert "/queue" in names
    assert "/help" in names

    print("command surface ok", t1.task_id, t2.task_id)

def test_main():
    main()


if __name__ == "__main__":
    main()
