from pathlib import Path

from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.services.task_service import TaskService
from mc_foreman.workers.queue_worker import QueueWorker


class MockConfig:
    execution_mode = "mock"


class MockBridge(ExecutionBridge):
    def __init__(self):
        super().__init__(MockConfig())


def build_app(db_path: Path):
    conn = get_connection(db_path)
    init_db(conn)
    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)
    worker = QueueWorker(task_service, MockBridge())
    return conn, task_service, queue_repo, worker


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "data" / "reset_test.sqlite3"

    reset_db_files(db_path)
    conn, task_service, queue_repo, worker = build_app(db_path)
    task_service.submit_task(theme="喷泉A", submitter_id="player1")
    conn.close()

    reset_db_files(db_path)
    conn, task_service, queue_repo, worker = build_app(db_path)
    row = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()
    assert int(row["c"]) == 0
    assert queue_repo.peek_next(conn) is None
    assert worker.tick() is None

    task = task_service.submit_task(theme="喷泉B", submitter_id="player2")
    completed = worker.tick()
    assert completed is not None
    assert completed.task_id == task.task_id
    assert completed.state == "completed"

    conn.close()
    reset_db_files(db_path)
    conn, task_service, queue_repo, worker = build_app(db_path)
    row = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()
    assert int(row["c"]) == 0
    assert worker.tick() is None

    print("reset flow ok", task.task_id)

def test_main():
    main()


if __name__ == "__main__":
    main()
