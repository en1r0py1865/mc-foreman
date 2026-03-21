from dataclasses import dataclass
from typing import Optional


@dataclass
class Task:
    task_id: str
    state: str
    submitter_type: str
    submitter_id: str
    source_command: str
    theme: str
    size: str
    created_at: int
    updated_at: int
    state_entered_at: int
    style: Optional[str] = None
    activity_tag: Optional[str] = None
    collab_note: Optional[str] = None
    queue_tier: Optional[str] = None
    review_path: Optional[str] = None
    review_result: Optional[str] = None
    zone_assignment: Optional[str] = None
    result_status: Optional[str] = None
    result_ref: Optional[str] = None


@dataclass
class TaskEvent:
    event_id: str
    task_id: str
    new_state: str
    trigger: str
    actor_type: str
    created_at: int
    prev_state: Optional[str] = None
    actor_id: Optional[str] = None
    detail_json: Optional[str] = None


@dataclass
class QueueEntry:
    task_id: str
    queue_tier: str
    enqueued_at: int
    submitter_id: str
    size: str
    priority_score: int = 0
    ttl_queued: Optional[int] = None
