from __future__ import annotations

import sqlite3
from dataclasses import asdict
from typing import Iterable, List, Optional

from mc_foreman.domain.models import Task
from mc_foreman.execution.zone_allocator import BuildZone


class TaskRepo:
    def insert(self, tx: sqlite3.Connection, task: Task) -> None:
        tx.execute(
            """
            INSERT INTO tasks (
              task_id, state, submitter_type, submitter_id, source_command, theme,
              style, size, activity_tag, collab_note, queue_tier, review_path,
              review_result, zone_assignment, result_status, result_ref,
              state_entered_at, created_at, updated_at
            ) VALUES (
              :task_id, :state, :submitter_type, :submitter_id, :source_command, :theme,
              :style, :size, :activity_tag, :collab_note, :queue_tier, :review_path,
              :review_result, :zone_assignment, :result_status, :result_ref,
              :state_entered_at, :created_at, :updated_at
            )
            """,
            asdict(task),
        )

    def get_by_id(self, conn: sqlite3.Connection, task_id: str) -> Optional[Task]:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return Task(**dict(row)) if row else None

    def update_state(self, tx: sqlite3.Connection, task_id: str, expected_state: str, **new_fields) -> int:
        assignments = ", ".join(f"{k} = :{k}" for k in new_fields.keys())
        params = dict(new_fields)
        params["task_id"] = task_id
        params["expected_state"] = expected_state
        cursor = tx.execute(
            f"UPDATE tasks SET {assignments} WHERE task_id = :task_id AND state = :expected_state",
            params,
        )
        return cursor.rowcount

    def list_by_submitter(self, conn: sqlite3.Connection, submitter_id: str, page: int = 1, page_size: int = 20) -> List[Task]:
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM tasks WHERE submitter_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (submitter_id, page_size, offset),
        ).fetchall()
        return [Task(**dict(r)) for r in rows]

    def count_active(self, conn: sqlite3.Connection, submitter_id: str, states: Iterable[str] = ("pending_review", "queued")) -> int:
        placeholders = ",".join("?" for _ in states)
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM tasks WHERE submitter_id = ? AND state IN ({placeholders})",
            (submitter_id, *states),
        ).fetchone()
        return int(row["c"])

    def next_zone_index(self, conn: sqlite3.Connection) -> int:
        rows = conn.execute(
            "SELECT zone_assignment FROM tasks WHERE zone_assignment IS NOT NULL"
        ).fetchall()
        highest = -1
        for row in rows:
            zone = BuildZone.from_assignment_str(row["zone_assignment"])
            if zone is not None:
                highest = max(highest, zone.zone_index)
        return highest + 1
