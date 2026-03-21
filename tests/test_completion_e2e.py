"""End-to-end test: submit → worker.tick → completion notifier delivers.

Verifies the full runtime wiring path:
1. RuntimeHook intercepts /build command
2. QueueWorker dequeues and executes (mock mode)
3. CompletionNotifier delivers result back through channel
4. /status returns completed state with result_ref
5. InterceptResult carries attachments for completed status queries
"""
from pathlib import Path

from mc_foreman.artifacts.result_bundle import load_result_bundle
from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.runtime.completion_notifier import CompletionNotifier
from mc_foreman.runtime.hook import InterceptResult, RuntimeHook
from mc_foreman.runtime.gateway import RuntimeGateway
from mc_foreman.runtime.bootstrap import bootstrap_runtime_hook, bootstrap_worker, reset_runtime_hook_cache


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "completion_e2e_test.sqlite3"
EXEC_DIR = Path(__file__).resolve().parents[1] / "data" / "execution_e2e_test"


class _MockConfig:
    execution_mode = "mock"
    execution_tmp_dir = EXEC_DIR


def _setup():
    reset_db_files(DB_PATH)
    EXEC_DIR.mkdir(parents=True, exist_ok=True)

    reset_runtime_hook_cache()
    hook = bootstrap_runtime_hook(db_path=DB_PATH)

    delivered = []
    notifier = CompletionNotifier(deliver_fn=lambda d: delivered.append(d))
    worker, task_service = bootstrap_worker(
        db_path=DB_PATH,
        completion_notifier=notifier,
    )

    conn = get_connection(DB_PATH)
    event_repo = EventRepo()

    return hook, worker, task_service, delivered, event_repo, conn


def test_full_build_to_completion():
    hook, worker, task_service, delivered, event_repo, conn = _setup()

    # Step 1: Submit via /build
    r = hook.intercept("/build 小亭子 --size small", user_id="player1")
    assert r.intercepted is True
    assert "任务已提交" in r.reply
    task_id = r.bot_result["data"]["task_id"]

    # Step 2: Worker dequeues, executes, and completes
    completed = worker.tick()
    assert completed is not None
    assert completed.state == "completed"
    assert completed.result_ref is not None

    # Step 3: Verify completion notifier was called — mock mode shows
    # simulation label, not the "建造完成 ✅" used for real builds.
    assert len(delivered) == 1
    delivery = delivered[0]
    assert delivery.success is True
    assert delivery.user_id == "player1"
    assert delivery.task_id == task_id
    assert "[模拟]" in delivery.reply_text, "mock mode should label delivery as simulated"
    assert "模拟执行" in delivery.reply_text
    # Step 4: Verify result_bundle manifest has no screenshot section
    bundle = load_result_bundle(completed.result_ref)
    assert "images" not in bundle

    # Step 5: Check /status returns completed with result_ref
    r2 = hook.intercept("/status --task-id %s" % task_id, user_id="player1")
    assert r2.intercepted is True
    assert "completed" in r2.reply or "状态" in r2.reply

    # Step 6: Verify event trail
    events = event_repo.list_by_task(conn, task_id)
    states = [e.new_state for e in events]
    assert states == ["pending_review", "queued", "building", "completed"], states

    print("  full_build_to_completion ok")


def test_completion_notifier_called_on_failure():
    """Worker.tick() with a failing bridge triggers _safe_notify and delivers to deliver_fn."""
    hook, worker, task_service, delivered, event_repo, conn = _setup()

    # Replace bridge with one that always fails
    from mc_foreman.execution.bridge import ExecutionResult

    class _FailingBridge:
        def execute(self, task):
            return ExecutionResult(success=False, reason="test_execution_failed")

    worker.bridge = _FailingBridge()

    # Submit a task
    r = hook.intercept("/build 石桥", user_id="player2")
    task_id = r.bot_result["data"]["task_id"]

    # worker.tick() should go through the failure path and call _safe_notify
    failed = worker.tick()
    assert failed is not None
    assert failed.state == "failed"

    # Verify the deliver_fn (from _setup) was called by worker's internal notifier
    assert len(delivered) == 1
    assert delivered[0].success is False
    assert delivered[0].task_id == task_id
    assert "建造失败" in delivered[0].reply_text
    print("  completion_notifier_called_on_failure ok")


def test_worker_tick_empty_queue():
    hook, worker, task_service, delivered, event_repo, conn = _setup()
    result = worker.tick()
    assert result is None
    assert len(delivered) == 0
    print("  worker_tick_empty_queue ok")


def test_multiple_tasks_sequential():
    hook, worker, task_service, delivered, event_repo, conn = _setup()

    # Submit 2 tasks from different users
    r1 = hook.intercept("/build 灯塔", user_id="user_a")
    r2 = hook.intercept("/build 石桥", user_id="user_b")
    assert r1.intercepted and r2.intercepted

    # Process both
    c1 = worker.tick()
    c2 = worker.tick()
    assert c1 is not None and c1.state == "completed"
    assert c2 is not None and c2.state == "completed"

    # Both should have notified
    assert len(delivered) == 2
    assert delivered[0].user_id == "user_a"
    assert delivered[1].user_id == "user_b"
    print("  multiple_tasks_sequential ok")


def test_intercept_result_attachments_for_status():
    hook, worker, task_service, delivered, event_repo, conn = _setup()

    # Build and complete
    r = hook.intercept("/build 花园", user_id="p1")
    task_id = r.bot_result["data"]["task_id"]
    worker.tick()

    # Status query — attachments are empty in the standalone core runtime
    r2 = hook.intercept("/status --task-id %s" % task_id, user_id="p1")
    assert r2.intercepted is True
    assert isinstance(r2.attachments, list)
    assert r2.attachments == []
    print("  intercept_result_attachments_for_status ok")


def main():
    tests = [
        test_full_build_to_completion,
        test_completion_notifier_called_on_failure,
        test_worker_tick_empty_queue,
        test_multiple_tasks_sequential,
        test_intercept_result_attachments_for_status,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print("  FAIL %s: %s" % (t.__name__, e))
            traceback.print_exc()
            failed += 1
    print("\ncompletion e2e: %d passed, %d failed" % (passed, failed))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
