from __future__ import annotations

import json
import time
import uuid
from dataclasses import replace
from typing import Optional, Tuple

from mc_foreman.domain.errors import ServiceException
from mc_foreman.domain.models import QueueEntry, Task, TaskEvent
from mc_foreman.execution.zone_allocator import allocate_zone, preflight_check
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo


def _now_ms() -> int:
    return int(time.time() * 1000)


def _id() -> str:
    return uuid.uuid4().hex


class TaskService:
    def __init__(self, conn, task_repo: TaskRepo, event_repo: EventRepo, queue_repo: QueueRepo):
        self.conn = conn
        self.task_repo = task_repo
        self.event_repo = event_repo
        self.queue_repo = queue_repo

    def list_my_tasks(self, submitter_id: str, page: int = 1, page_size: int = 5):
        return self.task_repo.list_by_submitter(self.conn, submitter_id, page=page, page_size=page_size)

    def get_queue_summary(self, submitter_id: Optional[str] = None, limit: int = 5) -> dict:
        items = self.queue_repo.list_public_summary(self.conn, limit=limit)
        total = self.queue_repo.count_all(self.conn)
        own_task_id = None
        own_position = None
        estimated_wait_minutes = None

        if submitter_id:
            tasks = self.task_repo.list_by_submitter(self.conn, submitter_id, page=1, page_size=20)
            own_queued = next((task for task in tasks if task.state == "queued"), None)
            if own_queued is not None:
                own_task_id = own_queued.task_id
                own_position = self.queue_repo.get_position(self.conn, own_task_id)
                if own_position is not None:
                    estimated_wait_minutes = max(1, own_position * 2)

        summaries = []
        for item in items:
            size_label = "小型" if item["size"] == "small" else "中型" if item["size"] == "medium" else "大型"
            summaries.append(
                {
                    "public_summary": f"一个{size_label}{item['theme']}",
                    "state": item["state"],
                }
            )

        return {
            "queue_length": total,
            "own_task_id": own_task_id,
            "own_position": own_position,
            "estimated_wait_minutes": estimated_wait_minutes,
            "items": summaries,
        }

    def _review(self, theme: str, size: str, submitter_id: str) -> Tuple[bool, str]:
        if not theme or len(theme.strip()) == 0 or len(theme) > 200:
            return False, "reject:empty_theme"
        if size not in {"small", "medium"}:
            return False, "reject:invalid_size"
        if self.task_repo.count_active(self.conn, submitter_id) >= 1:
            return False, "reject:rate_limit"
        return True, "pass"

    def submit_task(self, *, theme: str, submitter_id: str, size: str = "small", style: Optional[str] = None) -> Task:
        now = _now_ms()
        task = Task(
            task_id=_id(),
            state="pending_review",
            submitter_type="user",
            submitter_id=submitter_id,
            source_command="/build",
            theme=theme,
            style=style,
            size=size,
            created_at=now,
            updated_at=now,
            state_entered_at=now,
        )
        passed, review_result = self._review(theme=theme, size=size, submitter_id=submitter_id)
        with self.conn:
            self.task_repo.insert(self.conn, task)
            self.event_repo.insert(
                self.conn,
                TaskEvent(
                    event_id=_id(),
                    task_id=task.task_id,
                    prev_state=None,
                    new_state="pending_review",
                    trigger="create",
                    actor_type="user",
                    actor_id=submitter_id,
                    detail_json=None,
                    created_at=now,
                ),
            )
            if passed:
                next_state = "queued"
                zone = allocate_zone(self.task_repo.next_zone_index(self.conn))
                zone_ok, _issues = preflight_check(zone)
                zone_assignment = zone.to_assignment_str() if zone_ok else None
                self.task_repo.update_state(
                    self.conn,
                    task.task_id,
                    "pending_review",
                    state=next_state,
                    queue_tier="Q3",
                    review_path="auto",
                    review_result=review_result,
                    zone_assignment=zone_assignment,
                    state_entered_at=now,
                    updated_at=now,
                )
                self.queue_repo.insert(
                    self.conn,
                    QueueEntry(
                        task_id=task.task_id,
                        queue_tier="Q3",
                        enqueued_at=now,
                        submitter_id=submitter_id,
                        size=size,
                    ),
                )
                self.event_repo.insert(
                    self.conn,
                    TaskEvent(
                        event_id=_id(),
                        task_id=task.task_id,
                        prev_state="pending_review",
                        new_state="queued",
                        trigger="review",
                        actor_type="system",
                        actor_id=None,
                        detail_json=json.dumps({"review_result": review_result}),
                        created_at=now,
                    ),
                )
                return replace(task, state="queued", queue_tier="Q3", review_path="auto", review_result=review_result, zone_assignment=zone_assignment)
            else:
                self.task_repo.update_state(
                    self.conn,
                    task.task_id,
                    "pending_review",
                    state="rejected",
                    review_path="auto",
                    review_result=review_result,
                    state_entered_at=now,
                    updated_at=now,
                )
                self.event_repo.insert(
                    self.conn,
                    TaskEvent(
                        event_id=_id(),
                        task_id=task.task_id,
                        prev_state="pending_review",
                        new_state="rejected",
                        trigger="review",
                        actor_type="system",
                        actor_id=None,
                        detail_json=json.dumps({"review_result": review_result}),
                        created_at=now,
                    ),
                )
                raise ServiceException("FORBIDDEN", "主题内容未通过审核")

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.task_repo.get_by_id(self.conn, task_id)

    def cancel_task(self, task_id: str, actor_id: str) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise ServiceException("NOT_FOUND", "找不到该任务")
        if task.submitter_id != actor_id:
            raise ServiceException("FORBIDDEN", "无权取消该任务")
        if task.state != "queued":
            raise ServiceException("CONFLICT", "该任务当前不可取消")

        now = _now_ms()
        with self.conn:
            updated = self.task_repo.update_state(
                self.conn,
                task_id,
                "queued",
                state="cancelled",
                result_status="cancelled",
                state_entered_at=now,
                updated_at=now,
            )
            if updated == 0:
                raise ServiceException("CONFLICT", "该任务状态已变更，无法取消")
            self.queue_repo.delete(self.conn, task_id)
            self.event_repo.insert(
                self.conn,
                TaskEvent(
                    event_id=_id(),
                    task_id=task_id,
                    prev_state="queued",
                    new_state="cancelled",
                    trigger="cancel",
                    actor_type="user",
                    actor_id=actor_id,
                    detail_json=None,
                    created_at=now,
                ),
            )
        return replace(task, state="cancelled", result_status="cancelled", state_entered_at=now, updated_at=now)

    def dequeue_next(self) -> Optional[Task]:
        entry = self.queue_repo.peek_next(self.conn)
        if entry is None:
            return None
        task = self.get_task(entry.task_id)
        if task is None:
            return None

        now = _now_ms()
        with self.conn:
            updated = self.task_repo.update_state(
                self.conn,
                task.task_id,
                "queued",
                state="building",
                state_entered_at=now,
                updated_at=now,
            )
            if updated == 0:
                raise ServiceException("CONFLICT", "该任务状态已变更，无法出队")
            self.queue_repo.delete(self.conn, task.task_id)
            self.event_repo.insert(
                self.conn,
                TaskEvent(
                    event_id=_id(),
                    task_id=task.task_id,
                    prev_state="queued",
                    new_state="building",
                    trigger="dequeue",
                    actor_type="system",
                    actor_id=None,
                    detail_json=None,
                    created_at=now,
                ),
            )
        return replace(task, state="building", state_entered_at=now, updated_at=now)

    def complete_task(self, task_id: str, result_ref: Optional[str] = None) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise ServiceException("NOT_FOUND", "找不到该任务")
        now = _now_ms()
        with self.conn:
            updated = self.task_repo.update_state(
                self.conn,
                task_id,
                "building",
                state="completed",
                result_status="success",
                result_ref=result_ref,
                state_entered_at=now,
                updated_at=now,
            )
            if updated == 0:
                raise ServiceException("CONFLICT", "该任务状态已变更，无法完成")
            self.event_repo.insert(
                self.conn,
                TaskEvent(
                    event_id=_id(),
                    task_id=task_id,
                    prev_state="building",
                    new_state="completed",
                    trigger="complete",
                    actor_type="system",
                    actor_id=None,
                    detail_json=json.dumps({"result_ref": result_ref}),
                    created_at=now,
                ),
            )
        return replace(task, state="completed", result_status="success", result_ref=result_ref, state_entered_at=now, updated_at=now)

    def fail_task(self, task_id: str, reason: str) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise ServiceException("NOT_FOUND", "找不到该任务")
        now = _now_ms()
        with self.conn:
            updated = self.task_repo.update_state(
                self.conn,
                task_id,
                "building",
                state="failed",
                result_status="failed",
                state_entered_at=now,
                updated_at=now,
            )
            if updated == 0:
                raise ServiceException("CONFLICT", "该任务状态已变更，无法标记失败")
            self.event_repo.insert(
                self.conn,
                TaskEvent(
                    event_id=_id(),
                    task_id=task_id,
                    prev_state="building",
                    new_state="failed",
                    trigger="fail",
                    actor_type="system",
                    actor_id=None,
                    detail_json=json.dumps({"reason": reason}),
                    created_at=now,
                ),
            )
        return replace(task, state="failed", result_status="failed", state_entered_at=now, updated_at=now)
