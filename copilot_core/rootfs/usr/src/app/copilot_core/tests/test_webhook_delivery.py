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

        stats = queue._get_stats_snapshot()
        assert stats["enqueued_total"] == 1
        assert stats["dropped_total"] == 1
        assert stats["delivered_total"] == 0
        assert stats["failed_total"] == 0

    @patch("copilot_core.webhook_delivery.threading.Thread")
    def test_drop_oldest_policy_drops_oldest_and_accepts_new(self, mock_thread_cls) -> None:
        """Bei voller Queue verwirft drop_oldest den aeltesten Eintrag und nimmt neuen an."""
        mock_worker = MagicMock()
        mock_thread_cls.return_value = mock_worker

        queue = WebhookDeliveryQueue(
            send_func=lambda _envelope: None,
            worker_count=1,
            max_queue_size=2,
            backpressure_policy="drop_oldest",
        )

        assert queue.enqueue({"type": "first", "data": {}}) is True
        assert queue.enqueue({"type": "second", "data": {}}) is True
        assert queue.enqueue({"type": "third", "data": {}}) is True

        buffered = list(queue._queue.queue)  # noqa: SLF001
        assert [item["type"] for item in buffered] == ["second", "third"]
        assert queue._queue.unfinished_tasks == 2  # noqa: SLF001

        stats = queue._get_stats_snapshot()
        assert stats["enqueued_total"] == 3
        assert stats["dropped_total"] == 1

    @patch("copilot_core.webhook_delivery.threading.Thread")
    def test_block_timeout_policy_drops_after_timeout(self, mock_thread_cls) -> None:
        """block_timeout blockiert kurz und verwirft danach korrekt."""
        mock_worker = MagicMock()
        mock_thread_cls.return_value = mock_worker

        queue = WebhookDeliveryQueue(
            send_func=lambda _envelope: None,
            worker_count=1,
            max_queue_size=1,
            backpressure_policy="block_timeout",
            block_timeout_seconds=0.01,
        )

        assert queue.enqueue({"type": "first", "data": {}}) is True
        assert queue.enqueue({"type": "second", "data": {}}) is False

        stats = queue._get_stats_snapshot()
        assert stats["enqueued_total"] == 1
        assert stats["dropped_total"] == 1

    def test_stats_track_delivered_and_failed(self) -> None:
        calls = {"count": 0}

        def _send(_envelope: dict) -> None:
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("boom")

        queue = WebhookDeliveryQueue(
            send_func=_send,
            worker_count=1,
            max_queue_size=4,
            backpressure_policy="drop_newest",
        )
        queue.start()

        assert queue.enqueue({"type": "ok", "data": {}}) is True
        assert queue.enqueue({"type": "fail", "data": {}}) is True

        queue.stop(drain_timeout=1.0)

        stats = queue._get_stats_snapshot()
        assert stats["enqueued_total"] == 2
        assert stats["dropped_total"] == 0
        assert stats["delivered_total"] == 1
        assert stats["failed_total"] == 1
