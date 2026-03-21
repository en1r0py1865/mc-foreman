"""Completion notifier for delivering task results back through the channel.

After a task finishes building, the CompletionNotifier constructs a
delivery payload containing the reply text, then calls a delivery
function (provided by the channel adapter) to push results back to the user.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from mc_foreman.artifacts.result_bundle import load_result_bundle
from mc_foreman.domain.failure_map import user_facing_reason


@dataclass
class CompletionDelivery:
    """Payload delivered to the user when a task completes."""

    user_id: str
    task_id: str
    reply_text: str
    success: bool = True


class CompletionNotifier:
    """Builds and delivers completion payloads through a channel callback.

    The *deliver_fn* is a callable provided by the platform adapter::

        def deliver(delivery: CompletionDelivery) -> None:
            # e.g. send message via channel adapter
            ...

        notifier = CompletionNotifier(deliver_fn=deliver)
    """

    def __init__(self, deliver_fn: Optional[Callable[[CompletionDelivery], None]] = None):
        self._deliver_fn = deliver_fn
        self._history: List[CompletionDelivery] = []

    def notify(self, task, result_ref: Optional[str] = None, reason: Optional[str] = None) -> CompletionDelivery:
        """Build a CompletionDelivery from a completed task and deliver it.

        Args:
            task: A completed Task object.
            result_ref: Path to the result_bundle manifest JSON.
            reason: Internal failure reason code (for failed tasks).

        Returns:
            The CompletionDelivery that was sent.
        """
        verification_mode: str = ""
        if result_ref:
            bundle = load_result_bundle(result_ref)
            verification_mode = (bundle.get("verification") or {}).get("mode", "")

        success = task.state == "completed"
        is_mock = verification_mode == "mock"
        if success and is_mock:
            text = (
                "[模拟] 建造流程测试通过\n"
                "任务ID: %s\n主题: %s\n"
                "⚠️ 这是模拟执行，未连接真实 Minecraft 服务器，没有实际方块变化，也没有真实截图。"
            ) % (task.task_id, task.theme)
        elif success:
            text = "建造完成 ✅\n任务ID: %s\n主题: %s" % (task.task_id, task.theme)
        else:
            friendly = user_facing_reason(reason)
            text = "建造失败 ❌\n任务ID: %s\n主题: %s\n原因: %s" % (task.task_id, task.theme, friendly)

        delivery = CompletionDelivery(
            user_id=task.submitter_id,
            task_id=task.task_id,
            reply_text=text,
            success=success,
        )

        self._history.append(delivery)

        if self._deliver_fn is not None:
            self._deliver_fn(delivery)

        return delivery

    @property
    def history(self) -> List[CompletionDelivery]:
        """Delivered payloads (useful for testing)."""
        return list(self._history)
