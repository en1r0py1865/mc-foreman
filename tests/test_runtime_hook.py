"""Tests for RuntimeHook: command interception, pass-through, success/error,
and direct-chat oriented behaviour."""
from pathlib import Path

from mc_foreman.infra.db import reset_db_files
from mc_foreman.runtime import bootstrap_runtime_hook
from mc_foreman.runtime.bootstrap import reset_runtime_hook_cache


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "runtime_hook_test.sqlite3"


def make_hook():
    reset_db_files(DB_PATH)
    reset_runtime_hook_cache()
    return bootstrap_runtime_hook(db_path=DB_PATH)


# ── interception vs pass-through ──────────────────────────────────────

def test_slash_command_intercepted():
    hook = make_hook()
    r = hook.intercept("/help", user_id="u1")
    assert r.intercepted is True
    assert "/build" in r.reply
    assert r.bot_result is not None
    print("  slash_command_intercepted ok")


def test_plain_text_not_intercepted():
    hook = make_hook()
    r = hook.intercept("hello world", user_id="u1")
    assert r.intercepted is False
    assert r.reason == "not_mc_foreman_command"
    assert r.reply is None
    print("  plain_text_not_intercepted ok")


def test_unknown_slash_not_intercepted():
    hook = make_hook()
    r = hook.intercept("/foo", user_id="u1")
    assert r.intercepted is False
    print("  unknown_slash_not_intercepted ok")


def test_empty_text_not_intercepted():
    hook = make_hook()
    r = hook.intercept("", user_id="u1")
    assert r.intercepted is False
    print("  empty_text_not_intercepted ok")


# ── success replies ───────────────────────────────────────────────────

def test_build_success():
    hook = make_hook()
    r = hook.intercept("/build 小喷泉 --size small", user_id="u1")
    assert r.intercepted is True
    assert "任务已提交" in r.reply
    assert r.bot_result["ok"] is True
    assert r.bot_result["command"] == "/build"
    print("  build_success ok")


def test_queue_success():
    hook = make_hook()
    # submit a task first so queue has content
    hook.intercept("/build 亭子", user_id="u1")
    r = hook.intercept("/queue", user_id="u1")
    assert r.intercepted is True
    assert "当前队列长度" in r.reply
    print("  queue_success ok")


def test_mybuilds_success():
    hook = make_hook()
    hook.intercept("/build 石桥", user_id="u1")
    r = hook.intercept("/mybuilds", user_id="u1")
    assert r.intercepted is True
    assert "石桥" in r.reply
    print("  mybuilds_success ok")


def test_status_after_build():
    hook = make_hook()
    build = hook.intercept("/build 灯塔", user_id="u1")
    task_id = build.bot_result["data"]["task_id"]
    r = hook.intercept("/status --task-id %s" % task_id, user_id="u1")
    assert r.intercepted is True
    assert "queued" in r.reply or "状态" in r.reply
    print("  status_after_build ok")


# ── error replies ─────────────────────────────────────────────────────

def test_build_missing_size_value():
    hook = make_hook()
    r = hook.intercept("/build 小喷泉 --size", user_id="u1")
    assert r.intercepted is True
    assert r.bot_result["ok"] is False
    assert "参数有误" in r.reply
    print("  build_missing_size_value ok")


def test_cancel_no_args():
    hook = make_hook()
    r = hook.intercept("/cancel", user_id="u1")
    assert r.intercepted is True
    assert r.bot_result["ok"] is False
    assert "参数有误" in r.reply
    print("  cancel_no_args ok")


# ── direct-chat oriented behaviour ───────────────────────────────────

def test_group_chat_not_intercepted():
    hook = make_hook()
    r = hook.intercept("/help", user_id="u1", chat_type="group")
    assert r.intercepted is False
    print("  group_chat_not_intercepted ok")


def test_direct_chat_intercepted():
    hook = make_hook()
    r = hook.intercept("/help", user_id="u1", chat_type="direct")
    assert r.intercepted is True
    print("  direct_chat_intercepted ok")


def test_default_chat_type_is_direct():
    hook = make_hook()
    # no chat_type argument → defaults to "direct" → should intercept
    r = hook.intercept("/help", user_id="u1")
    assert r.intercepted is True
    print("  default_chat_type_is_direct ok")


# ── to_dict serialisation ────────────────────────────────────────────

def test_to_dict_intercepted():
    hook = make_hook()
    r = hook.intercept("/help", user_id="u1")
    d = r.to_dict()
    assert d["intercepted"] is True
    assert "reply" in d
    assert "bot_result" in d
    assert "reason" not in d
    print("  to_dict_intercepted ok")


def test_to_dict_not_intercepted():
    hook = make_hook()
    r = hook.intercept("hello", user_id="u1")
    d = r.to_dict()
    assert d["intercepted"] is False
    assert d["reason"] == "not_mc_foreman_command"
    assert "reply" not in d
    print("  to_dict_not_intercepted ok")


# ── runner ────────────────────────────────────────────────────────────

def main():
    tests = [
        test_slash_command_intercepted,
        test_plain_text_not_intercepted,
        test_unknown_slash_not_intercepted,
        test_empty_text_not_intercepted,
        test_build_success,
        test_queue_success,
        test_mybuilds_success,
        test_status_after_build,
        test_build_missing_size_value,
        test_cancel_no_args,
        test_group_chat_not_intercepted,
        test_direct_chat_intercepted,
        test_default_chat_type_is_direct,
        test_to_dict_intercepted,
        test_to_dict_not_intercepted,
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
    print("\nruntime hook: %d passed, %d failed" % (passed, failed))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
