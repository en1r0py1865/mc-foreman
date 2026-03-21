from pathlib import Path

from mc_foreman.artifacts.result_bundle import load_result_bundle
from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.handlers.build import BuildHandler
from mc_foreman.handlers.status import StatusHandler
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.runtime.completion_notifier import CompletionNotifier
from mc_foreman.services.task_service import TaskService
from mc_foreman.workers.queue_worker import QueueWorker


class MockConfig:
    execution_mode = "mock"


class MockBridge(ExecutionBridge):
    def __init__(self):
        super().__init__(MockConfig())


def main():
    db_path = Path(__file__).resolve().parents[1] / "data" / "completion_delivery_test.sqlite3"
    result_root = Path(__file__).resolve().parents[1] / "data" / "completion_results"
    reset_db_files(db_path)

    conn = get_connection(db_path)
    init_db(conn)
    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    deliveries = []
    notifier = CompletionNotifier(deliver_fn=lambda d: deliveries.append(d))
    worker = QueueWorker(
        task_service,
        MockBridge(),
        completion_notifier=notifier,
    )

    build = BuildHandler(task_service).handle(theme="观景塔", submitter_id="user1", size="small")
    task_id = build["data"]["task_id"]
    completed = worker.tick()
    assert completed is not None
    assert completed.state == "completed"
    assert completed.result_ref is not None

    bundle = load_result_bundle(completed.result_ref)
    assert "images" not in bundle

    status = StatusHandler(task_service, task_repo).handle(submitter_id="user1", task_id=task_id)
    assert "image_paths" not in status["data"]

    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.success is True
    # Mock mode: delivery strips images and labels as simulated
    assert delivery.success is True
    assert "[模拟]" in delivery.reply_text, "mock delivery should be labeled as simulated"

    print("completion delivery ok", task_id)

def test_main():
    main()


if __name__ == "__main__":
    main()
