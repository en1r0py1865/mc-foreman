from pathlib import Path

from mc_foreman.infra.db import reset_db_files
from mc_foreman.runtime.session_integration import handle_current_session_message


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "session_integration_test.sqlite3"


def main():
    reset_db_files(DB_PATH)

    help_reply = handle_current_session_message(
        text="/help",
        user_id="ou_session1",
        channel="feishu",
        chat_type="direct",
        db_path=DB_PATH,
    )
    assert help_reply["handled"] is True
    assert "/build" in help_reply["reply_text"]
    assert isinstance(help_reply["attachments"], list)

    build_reply = handle_current_session_message(
        text="/build 观景塔 --size small",
        user_id="ou_session1",
        channel="feishu",
        chat_type="direct",
        db_path=DB_PATH,
    )
    assert build_reply["handled"] is True
    assert "任务已提交" in build_reply["reply_text"]

    plain_text = handle_current_session_message(
        text="四合院",
        user_id="ou_session2",
        channel="feishu",
        chat_type="direct",
        db_path=DB_PATH,
    )
    assert plain_text["handled"] is False
    assert plain_text["normalized_text"] == "四合院"

    passthrough = handle_current_session_message(
        text="你好",
        user_id="ou_session1",
        channel="feishu",
        chat_type="direct",
        db_path=DB_PATH,
    )
    assert passthrough["handled"] is False
    assert passthrough["reply_text"] is None

    group_passthrough = handle_current_session_message(
        text="/help",
        user_id="ou_session1",
        channel="feishu",
        chat_type="group",
        db_path=DB_PATH,
    )
    assert group_passthrough["handled"] is False

    bad = handle_current_session_message(
        text="/build 观景塔 --size",
        user_id="ou_session1",
        channel="feishu",
        chat_type="direct",
        db_path=DB_PATH,
    )
    assert bad["handled"] is True
    assert "参数有误" in bad["reply_text"]
    assert isinstance(bad["attachments"], list)

    print("session integration ok")

def test_main():
    main()


if __name__ == "__main__":
    main()
