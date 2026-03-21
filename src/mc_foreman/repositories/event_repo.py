from __future__ import annotations

import sqlite3
from dataclasses import asdict
from typing import List

from mc_foreman.domain.models import TaskEvent


class EventRepo:
    def insert(self, tx: sqlite3.Connection, event: TaskEvent) -> None:
        tx.execute(
            """
            INSERT INTO task_events (
              event_id, task_id, prev_state, new_state, trigger,
              actor_type, actor_id, detail_json, created_at
            ) VALUES (
              :event_id, :task_id, :prev_state, :new_state, :trigger,
              :actor_type, :actor_id, :detail_json, :created_at
            )
            """,
            asdict(event),
        )

    def list_by_task(self, conn: sqlite3.Connection, task_id: str) -> List[TaskEvent]:
        rows = conn.execute(
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        ).fetchall()
        return [TaskEvent(**dict(r)) for r in rows]
