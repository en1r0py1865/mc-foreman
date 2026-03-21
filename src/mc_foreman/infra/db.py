from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union


SCHEMA_SQL = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  state TEXT NOT NULL CHECK (state IN ('pending_review','queued','building','completed','rejected','cancelled','failed')),
  submitter_type TEXT NOT NULL CHECK (submitter_type IN ('user','agent','admin')),
  submitter_id TEXT NOT NULL,
  source_command TEXT NOT NULL,
  theme TEXT NOT NULL,
  style TEXT,
  size TEXT NOT NULL CHECK (size IN ('small','medium','large')),
  activity_tag TEXT,
  collab_note TEXT,
  queue_tier TEXT CHECK (queue_tier IN ('Q1','Q2','Q3','Q4') OR queue_tier IS NULL),
  review_path TEXT CHECK (review_path IN ('auto','strategy','human') OR review_path IS NULL),
  review_result TEXT,
  zone_assignment TEXT,
  result_status TEXT,
  result_ref TEXT,
  state_entered_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS task_events (
  event_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  prev_state TEXT,
  new_state TEXT NOT NULL,
  trigger TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  detail_json TEXT,
  created_at INTEGER NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS queue_entries (
  task_id TEXT PRIMARY KEY,
  queue_tier TEXT NOT NULL,
  priority_score INTEGER NOT NULL DEFAULT 0,
  enqueued_at INTEGER NOT NULL,
  ttl_queued INTEGER,
  submitter_id TEXT NOT NULL,
  size TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_submitter_state ON tasks(submitter_id, state);
CREATE INDEX IF NOT EXISTS idx_tasks_state_updated ON tasks(state, updated_at);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_task_events_task_created ON task_events(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_queue_entries_tier_score_time ON queue_entries(queue_tier, priority_score DESC, enqueued_at ASC);
CREATE INDEX IF NOT EXISTS idx_queue_entries_submitter ON queue_entries(submitter_id);
"""


def get_connection(db_path: Union[str, Path]) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def reset_db_files(db_path: Union[str, Path]) -> Path:
    path = Path(db_path)
    for suffix in ("", "-wal", "-shm"):
        target = path if suffix == "" else path.parent / (path.name + suffix)
        target.unlink(missing_ok=True)
    return path
