from pathlib import Path
from mc_foreman.domain.models import Task
from mc_foreman.handlers.status import StatusHandler
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.runtime.completion_notifier import CompletionNotifier
from mc_foreman.services.task_service import TaskService


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "failure_visibility_test.sqlite3"


def _make_task(task_id="t1", state="failed", theme="石桥", submitter_id="u1"):
    now = 1000000
    return Task(
        task_id=task_id,
        state=state,
        submitter_type="user",
        submitter_id=submitter_id,
        source_command="/build",
        theme=theme,
        size="small",
        created_at=now,
        updated_at=now,
        state_entered_at=now,
    )


def test_completion_failure_message():
    notifier = CompletionNotifier()
    task = _make_task(state="failed")
    delivery = notifier.notify(task, reason="rcon_send_failed")
    assert "建造失败" in delivery.reply_text
    assert "向游戏服务器发送命令失败" in delivery.reply_text
    assert "rcon_send_failed" not in delivery.reply_text
    print("  completion_failure_message ok")


def test_status_failure_message_and_code():
    reset_db_files(DB_PATH)
    conn = get_connection(DB_PATH)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    task = task_service.submit_task(theme="石桥", submitter_id="u1")
    dequeued = task_service.dequeue_next()
    assert dequeued is not None
    failed = task_service.fail_task(task.task_id, reason="command_extraction_failed")
    assert failed.state == "failed"

    handler = StatusHandler(task_service, task_repo, event_repo=event_repo)
    result = handler.handle(submitter_id="u1", task_id=task.task_id)
    data = result["data"]
    assert data["failure_code"] == "command_extraction_failed"
    assert "提取有效命令" in data["failure_reason"]
    print("  status_failure_message_and_code ok")


def test_completed_delivery_has_no_attachments():
    notifier = CompletionNotifier()
    task = _make_task(task_id="t2", state="completed", theme="凉亭")
    delivery = notifier.notify(task, result_ref=None)
    assert delivery.success is True
    print("  completed_delivery_has_no_attachments ok")


def main():
    tests = [
        test_completion_failure_message,
        test_status_failure_message_and_code,
        test_completed_delivery_has_no_attachments,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print("  FAIL %s: %s" % (t.__name__, e))
            failed += 1
    print("\nfailure visibility: %d passed, %d failed" % (passed, failed))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
