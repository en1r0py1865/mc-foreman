from pathlib import Path

from mc_foreman.domain.errors import ServiceException
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.services.task_service import TaskService


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "data" / "smoke_test.sqlite3"
    reset_db_files(db_path)

    conn = get_connection(db_path)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    task = task_service.submit_task(theme="小木屋", submitter_id="player1")
    assert task.state == "queued", task

    saved = task_service.get_task(task.task_id)
    assert saved is not None
    assert saved.state == "queued"

    events = event_repo.list_by_task(conn, task.task_id)
    assert len(events) == 2, events
    assert events[0].new_state == "pending_review"
    assert events[1].new_state == "queued"

    queued = queue_repo.peek_next(conn)
    assert queued is not None
    assert queued.task_id == task.task_id

    conn.close()
    reset_db_files(db_path)
    conn = get_connection(db_path)
    init_db(conn)

    row = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()
    assert int(row["c"]) == 0
    assert queue_repo.peek_next(conn) is None

    print("smoke ok", task.task_id)


def test_main():
    main()


def test_submit_empty_theme_rejected():
    """submit_task with empty theme raises ServiceException(FORBIDDEN)."""
    db_path = Path(__file__).resolve().parents[1] / "data" / "smoke_reject_test.sqlite3"
    reset_db_files(db_path)
    conn = get_connection(db_path)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    try:
        task_service.submit_task(theme="", submitter_id="p1")
        assert False, "empty theme should be rejected"
    except ServiceException as exc:
        assert exc.code == "FORBIDDEN"

    # The raise inside `with self.conn:` rolls back the transaction,
    # so no task or queue entry is persisted for rejected submissions.
    row = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()
    assert int(row["c"]) == 0
    assert queue_repo.peek_next(conn) is None
    conn.close()


def test_submit_rate_limited():
    """Second submission from same user while first is queued raises ServiceException."""
    db_path = Path(__file__).resolve().parents[1] / "data" / "smoke_ratelimit_test.sqlite3"
    reset_db_files(db_path)
    conn = get_connection(db_path)
    init_db(conn)

    task_repo = TaskRepo()
    event_repo = EventRepo()
    queue_repo = QueueRepo()
    task_service = TaskService(conn, task_repo, event_repo, queue_repo)

    first = task_service.submit_task(theme="亭子", submitter_id="p1")
    assert first.state == "queued"

    try:
        task_service.submit_task(theme="石桥", submitter_id="p1")
        assert False, "second submission should be rate-limited"
    except ServiceException as exc:
        assert exc.code == "FORBIDDEN"

    conn.close()


if __name__ == "__main__":
    main()
