from pathlib import Path

from mc_foreman.artifacts.result_bundle import load_result_bundle
from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.services.task_service import TaskService
from mc_foreman.workers.queue_worker import QueueWorker


class MockConfig:
    execution_mode = "mock"
    execution_tmp_dir = Path(__file__).resolve().parents[1] / "data" / "execution_test"


class MockBridge(ExecutionBridge):
    def __init__(self):
        super().__init__(MockConfig())


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "data" / "worker_test.sqlite3"
    reset_db_files(db_path)

    conn = get_connection(db_path)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)
    worker = QueueWorker(task_service, MockBridge())

    task = task_service.submit_task(theme="石头喷泉", submitter_id="player1")
    assert task.state == "queued"

    completed = worker.tick()
    assert completed is not None
    assert completed.state == "completed"

    saved = task_service.get_task(task.task_id)
    assert saved is not None
    assert saved.state == "completed"
    assert saved.result_ref is not None
    bundle = load_result_bundle(saved.result_ref)
    assert "images" not in bundle

    events = event_repo.list_by_task(conn, task.task_id)
    states = [e.new_state for e in events]
    assert states == ["pending_review", "queued", "building", "completed"], states

    print("worker flow ok", task.task_id)

def test_main():
    main()


def test_worker_tick_execution_failure():
    """Worker.tick() with a failing bridge transitions task to 'failed'."""
    from mc_foreman.execution.bridge import ExecutionResult

    db_path = Path(__file__).resolve().parents[1] / "data" / "worker_fail_test.sqlite3"
    reset_db_files(db_path)

    conn = get_connection(db_path)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    class FailBridge:
        def execute(self, task):
            return ExecutionResult(success=False, reason="generation_failed")

    worker = QueueWorker(task_service, FailBridge())

    task = task_service.submit_task(theme="测试亭", submitter_id="p1")
    assert task.state == "queued"

    failed = worker.tick()
    assert failed is not None
    assert failed.state == "failed"

    # Verify event trail includes "failed"
    events = event_repo.list_by_task(conn, task.task_id)
    states = [e.new_state for e in events]
    assert states == ["pending_review", "queued", "building", "failed"], states

    conn.close()


def test_worker_tick_empty_queue():
    """Worker.tick() returns None when queue is empty."""
    db_path = Path(__file__).resolve().parents[1] / "data" / "worker_empty_test.sqlite3"
    reset_db_files(db_path)

    conn = get_connection(db_path)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)
    worker = QueueWorker(task_service, MockBridge())

    result = worker.tick()
    assert result is None

    conn.close()


if __name__ == "__main__":
    main()
