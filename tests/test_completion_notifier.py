"""Tests for CompletionNotifier."""
import tempfile
from pathlib import Path

from mc_foreman.artifacts.result_bundle import build_result_bundle
from mc_foreman.domain.models import Task
from mc_foreman.runtime.completion_notifier import CompletionDelivery, CompletionNotifier


def _make_task(task_id="t1", state="completed", theme="小喷泉", submitter_id="u1"):
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


def _make_bundle(tmp_dir, task_id="t1", theme="小喷泉"):
    return build_result_bundle(
        output_root=Path(tmp_dir),
        task_id=task_id,
        theme=theme,
        commands_path="mock://t1",
    )


def test_notify_completed_task():
    delivered = []
    notifier = CompletionNotifier(deliver_fn=lambda d: delivered.append(d))
    task = _make_task(state="completed")
    with tempfile.TemporaryDirectory() as tmp:
        result_ref = _make_bundle(tmp)
        delivery = notifier.notify(task, result_ref=result_ref)
    assert delivery.success is True
    assert delivery.user_id == "u1"
    assert delivery.task_id == "t1"
    assert delivery.success is True
    assert "建造完成" in delivery.reply_text
    assert len(delivered) == 1
    print("  notify_completed_task ok")


def test_notify_failed_task():
    delivered = []
    notifier = CompletionNotifier(deliver_fn=lambda d: delivered.append(d))
    task = _make_task(state="failed")
    delivery = notifier.notify(task, result_ref=None)
    assert delivery.success is False
    assert "建造失败" in delivery.reply_text
    assert len(delivered) == 1
    print("  notify_failed_task ok")


def test_notify_without_deliver_fn():
    notifier = CompletionNotifier(deliver_fn=None)
    task = _make_task(state="completed")
    delivery = notifier.notify(task, result_ref=None)
    assert delivery.success is True
    assert len(notifier.history) == 1
    print("  notify_without_deliver_fn ok")


def test_history_accumulates():
    notifier = CompletionNotifier()
    for i in range(3):
        task = _make_task(task_id=f"t{i}", state="completed")
        notifier.notify(task, result_ref=None)
    assert len(notifier.history) == 3
    print("  history_accumulates ok")


def test_notify_with_missing_result_ref():
    notifier = CompletionNotifier()
    task = _make_task(state="completed")
    delivery = notifier.notify(task, result_ref="/nonexistent/path.json")
    assert delivery.success is True
    print("  notify_with_missing_result_ref ok")


def test_delivery_dataclass_fields():
    d = CompletionDelivery(user_id="u1", task_id="t1", reply_text="hello")
    assert d.success is True
    assert d.reply_text == "hello"
    print("  delivery_dataclass_fields ok")


def main():
    tests = [
        test_notify_completed_task,
        test_notify_failed_task,
        test_notify_without_deliver_fn,
        test_history_accumulates,
        test_notify_with_missing_result_ref,
        test_delivery_dataclass_fields,
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
    print("\ncompletion notifier: %d passed, %d failed" % (passed, failed))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
