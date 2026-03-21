from __future__ import annotations

import sqlite3
from dataclasses import asdict
from typing import Dict, List, Optional

from mc_foreman.domain.models import QueueEntry


class QueueRepo:
    def insert(self, tx: sqlite3.Connection, entry: QueueEntry) -> None:
        tx.execute(
            """
            INSERT INTO queue_entries (
              task_id, queue_tier, priority_score, enqueued_at, ttl_queued, submitter_id, size
            ) VALUES (
              :task_id, :queue_tier, :priority_score, :enqueued_at, :ttl_queued, :submitter_id, :size
            )
            """,
            asdict(entry),
        )

    def delete(self, tx: sqlite3.Connection, task_id: str) -> int:
        cursor = tx.execute("DELETE FROM queue_entries WHERE task_id = ?", (task_id,))
        return cursor.rowcount

    def peek_next(self, conn: sqlite3.Connection, queue_tier: Optional[str] = None) -> Optional[QueueEntry]:
        if queue_tier:
            row = conn.execute(
                "SELECT * FROM queue_entries WHERE queue_tier = ? ORDER BY priority_score DESC, enqueued_at ASC LIMIT 1",
                (queue_tier,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM queue_entries ORDER BY priority_score DESC, enqueued_at ASC LIMIT 1"
            ).fetchone()
        return QueueEntry(**dict(row)) if row else None

    def count_all(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COUNT(*) AS c FROM queue_entries").fetchone()
        return int(row["c"])

    def get_position(self, conn: sqlite3.Connection, task_id: str) -> Optional[int]:
        rows = conn.execute(
            "SELECT task_id FROM queue_entries ORDER BY priority_score DESC, enqueued_at ASC"
        ).fetchall()
        for idx, row in enumerate(rows, 1):
            if row["task_id"] == task_id:
                return idx
        return None

    def list_public_summary(self, conn: sqlite3.Connection, limit: int = 5) -> List[Dict[str, object]]:
        rows = conn.execute(
            """
            SELECT q.task_id, q.enqueued_at, t.theme, t.size, t.state
            FROM queue_entries q
            JOIN tasks t ON t.task_id = q.task_id
            ORDER BY q.priority_score DESC, q.enqueued_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
