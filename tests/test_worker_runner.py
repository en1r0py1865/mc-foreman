from pathlib import Path

from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.runtime.worker_runner import WorkerRunner
from mc_foreman.services.task_service import TaskService
from mc_foreman.workers.queue_worker import QueueWorker


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "worker_runner_test.sqlite3"
EXEC_DIR = Path(__file__).resolve().parents[1] / "data" / "worker_runner_exec"


class MockConfig:
    execution_mode = "mock"
    execution_tmp_dir = EXEC_DIR


def _setup():
    reset_db_files(DB_PATH)
    conn = get_connection(DB_PATH)
    init_db(conn)
    task_service = TaskService(conn, TaskRepo(), EventRepo(), QueueRepo())
    bridge = ExecutionBridge(MockConfig())
    worker = QueueWorker(task_service, bridge)
    return task_service, WorkerRunner(worker)


def test_runner_processes_until_empty():
    svc, runner = _setup()
    svc.submit_task(theme="桥", submitter_id="u1")
    svc.submit_task(theme="塔", submitter_id="u2")
    summary = runner.run(run_until_empty=True, max_ticks=10)
    assert summary.processed == 2
    assert len(summary.completed_task_ids) == 2
    print("  runner_processes_until_empty ok")


def test_runner_single_tick_mode():
    svc, runner = _setup()
    svc.submit_task(theme="凉亭", submitter_id="u1")
    svc.submit_task(theme="花园", submitter_id="u2")
    summary = runner.run(run_until_empty=False, max_ticks=10)
    assert summary.processed == 1
    assert len(summary.completed_task_ids) == 1
    print("  runner_single_tick_mode ok")


def main():
    test_runner_processes_until_empty()
    test_runner_single_tick_mode()
    print("\nworker runner tests passed ✅")


if __name__ == "__main__":
    main()
