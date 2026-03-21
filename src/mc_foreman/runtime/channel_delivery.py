"""Host-facing auto-delivery callback for completion events.

Provides a structured interface so that host runtimes can receive and
deliver build completion results through their native channel without
modifying the core workflow engine.

Fully automated in-repo
~~~~~~~~~~~~~~~~~~~~~~~~
- Worker dequeues, executes, and completes the task.
- CompletionNotifier builds a ``CompletionDelivery`` payload.
- ``ChannelDeliveryCallback.on_delivery`` receives a formatted
  ``ChannelDeliveryEnvelope`` ready for channel transmission.
- ``RecordingDeliveryCallback`` captures every envelope for testing.

Requires host runtime hookup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- Actual message sending (chat API, platform runtime reply, etc.).
- User notification routing (push notifications, webhooks, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from mc_foreman.runtime.completion_notifier import CompletionDelivery


# ---------------------------------------------------------------------------
# Envelope – the structured payload passed to the host callback
# ---------------------------------------------------------------------------

@dataclass
class ChannelDeliveryEnvelope:
    """Formatted delivery ready for channel transmission.

    Fields mirror ``CompletionDelivery`` but add *channel* and *metadata*
    so the host can route and enrich the delivery for its platform.
    """

    user_id: str
    task_id: str
    text: str
    success: bool = True
    channel: str = "default"
    metadata: Dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Callback interface
# ---------------------------------------------------------------------------

class ChannelDeliveryCallback:
    """Base class for host-facing auto-delivery of completion events.

    Subclass and override :meth:`on_delivery` to integrate with your
    platform's message delivery system::

        class SlackDelivery(ChannelDeliveryCallback):
            def on_delivery(self, envelope):
                slack_client.post(envelope.channel, envelope.text, ...)
                return True

        callback = SlackDelivery()
        worker, svc = bootstrap_worker(channel_delivery=callback)
    """

    def on_delivery(self, envelope):
        # type: (ChannelDeliveryEnvelope) -> bool
        """Called when a task completes or fails.

        Args:
            envelope: Structured delivery payload.

        Returns:
            ``True`` if delivery succeeded, ``False`` otherwise.
        """
        raise NotImplementedError("subclass must implement on_delivery")

    def as_deliver_fn(self, channel="default"):
        # type: (str) -> Callable[[CompletionDelivery], bool]
        """Return a ``deliver_fn`` compatible with CompletionNotifier.

        This bridges the structured callback interface with the simple
        callable expected by :class:`CompletionNotifier`.
        """
        def _deliver(delivery):
            # type: (CompletionDelivery) -> bool
            envelope = ChannelDeliveryEnvelope(
                user_id=delivery.user_id,
                task_id=delivery.task_id,
                text=delivery.reply_text,
                success=delivery.success,
                channel=channel,
                metadata={},
            )
            return self.on_delivery(envelope)
        return _deliver


# ---------------------------------------------------------------------------
# Built-in implementations
# ---------------------------------------------------------------------------

class RecordingDeliveryCallback(ChannelDeliveryCallback):
    """Records all envelopes for testing and verification.

    Usage::

        recorder = RecordingDeliveryCallback()
        worker, svc = bootstrap_worker(channel_delivery=recorder)
        # ... submit and tick ...
        assert len(recorder.envelopes) == 1
        assert recorder.envelopes[0].success is True
    """

    def __init__(self):
        # type: () -> None
        self.envelopes = []  # type: List[ChannelDeliveryEnvelope]

    def on_delivery(self, envelope):
        # type: (ChannelDeliveryEnvelope) -> bool
        self.envelopes.append(envelope)
        return True


class LoggingDeliveryCallback(ChannelDeliveryCallback):
    """Prints delivery info to stdout — useful for demos and debugging."""

    def on_delivery(self, envelope):
        # type: (ChannelDeliveryEnvelope) -> bool
        status = "SUCCESS" if envelope.success else "FAILED"
        print("[channel-delivery] %s task=%s user=%s channel=%s" % (
            status,
            envelope.task_id[:8],
            envelope.user_id,
            envelope.channel,
        ))
        if envelope.text:
            for line in envelope.text.split("\n"):
                print("  | %s" % line)
        return True
