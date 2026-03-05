"""Basistests fuer die WebhookDeliveryQueue (PS-P0-009)."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from copilot_core.webhook_delivery import WebhookDeliveryQueue


class TestWebhookDeliveryQueueConfig:
    def test_invalid_policy_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported backpressure_policy"):
            WebhookDeliveryQueue(
                send_func=lambda _envelope: None,
                backpressure_policy="unsupported-policy",
            )


class TestWebhookDeliveryQueueWorkers:
    @patch("copilot_core.webhook_delivery.threading.Thread")
    def test_fixed_worker_count_no_thread_per_event(self, mock_thread_cls) -> None:
        """start() erstellt genau worker_count Threads; enqueue() startet keine neuen."""
        mock_worker = MagicMock()
        mock_thread_cls.return_value = mock_worker

        queue = WebhookDeliveryQueue(
            send_func=lambda _envelope: None,
            worker_count=3,
            max_queue_size=16,
            backpressure_policy="drop_newest",
        )

        queue.start()
        assert mock_thread_cls.call_count == 3

        assert queue.enqueue({"type": "a", "data": {}}) is True
        assert queue.enqueue({"type": "b", "data": {}}) is True

        # Kein Thread-pro-Event Muster
        assert mock_thread_cls.call_count == 3


class TestWebhookDeliveryQueueBehavior:
    def test_enqueue_is_delivered_single_attempt(self) -> None:
        delivered: list[dict] = []
        delivered_event = threading.Event()

        def _send(envelope: dict) -> None:
            delivered.append(envelope)
            delivered_event.set()

        queue = WebhookDeliveryQueue(
            send_func=_send,
            worker_count=1,
            max_queue_size=8,
        )
        queue.start()

        envelope = {"type": "mood_changed", "data": {"mood": "focus"}}
        assert queue.enqueue(envelope) is True

        assert delivered_event.wait(timeout=1.0), "delivery worker did not process envelope"
        queue.stop(drain_timeout=1.0)

        assert delivered == [envelope]

    @patch("copilot_core.webhook_delivery.threading.Thread")
    def test_drop_newest_policy_when_full(self, mock_thread_cls) -> None:
        """Bei voller Queue wird das neueste Event verworfen (drop_newest)."""
        mock_worker = MagicMock()
        mock_thread_cls.return_value = mock_worker

        queue = WebhookDeliveryQueue(
            send_func=lambda _envelope: None,
            worker_count=1,
            max_queue_size=1,
            backpressure_policy="drop_newest",
        )

        assert queue.enqueue({"type": "first", "data": {}}) is True
        assert queue.enqueue({"type": "second", "data": {}}) is False
