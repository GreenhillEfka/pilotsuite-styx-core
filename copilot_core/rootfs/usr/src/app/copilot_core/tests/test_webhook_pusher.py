"""Tests fuer den Webhook Pusher.

Testet Envelope-Format, disabled/enabled Zustand, Queue-Integration und HTTP-Format.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from copilot_core.webhook_pusher import WebhookPusher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pusher() -> WebhookPusher:
    return WebhookPusher("http://localhost:8123/api/webhook/test", "secret-token")


@pytest.fixture
def disabled_pusher() -> WebhookPusher:
    return WebhookPusher("", "")


# ---------------------------------------------------------------------------
# Enabled / Disabled
# ---------------------------------------------------------------------------

class TestEnabled:

    def test_enabled_with_url(self):
        p = WebhookPusher("http://example.test/hook", "token")
        assert p.enabled is True
        assert p._delivery_queue is not None

    def test_disabled_without_url(self, disabled_pusher):
        assert disabled_pusher.enabled is False
        assert disabled_pusher._delivery_queue is None

    def test_disabled_empty_string(self):
        p = WebhookPusher("", "token")
        assert p.enabled is False


# ---------------------------------------------------------------------------
# Envelope Format
# ---------------------------------------------------------------------------

class TestEnvelopeFormat:

    def test_mood_changed_envelope(self, pusher):
        """push_mood_changed sendet korrektes Envelope-Format."""
        pusher._send_envelope = MagicMock()
        pusher.push_mood_changed("relax", 0.85)
        pusher._send_envelope.assert_called_once_with(
            "mood_changed",
            {"mood": "relax", "confidence": 0.85},
        )

    def test_neuron_update_envelope(self, pusher):
        """push_neuron_update sendet korrektes Envelope-Format."""
        pusher._send_envelope = MagicMock()
        result = {"dominant_mood": "focus", "confidence": 0.72}
        pusher.push_neuron_update(result)
        pusher._send_envelope.assert_called_once_with("neuron_update", result)

    def test_suggestion_envelope(self, pusher):
        """push_suggestion sendet korrektes Envelope-Format."""
        pusher._send_envelope = MagicMock()
        suggestion = {"action": "dim_lights", "reason": "bedtime"}
        pusher.push_suggestion(suggestion)
        pusher._send_envelope.assert_called_once_with("suggestion", suggestion)


# ---------------------------------------------------------------------------
# Queue Integration
# ---------------------------------------------------------------------------

class TestQueueIntegration:

    def test_no_enqueue_when_disabled(self, disabled_pusher):
        """Kein Queue-Write wenn Pusher deaktiviert."""
        disabled_pusher.push_mood_changed("relax", 0.5)
        assert disabled_pusher._delivery_queue is None

    def test_enqueue_when_enabled(self, pusher):
        """Enabled Pusher enqueued Envelope in DeliveryQueue."""
        queue_mock = MagicMock()
        queue_mock.enqueue.return_value = True
        pusher._delivery_queue = queue_mock

        pusher.push_mood_changed("relax", 0.5)

        queue_mock.enqueue.assert_called_once_with(
            {"type": "mood_changed", "data": {"mood": "relax", "confidence": 0.5}}
        )

    def test_stop_forwards_to_queue(self, pusher):
        queue_mock = MagicMock()
        pusher._delivery_queue = queue_mock

        pusher.stop(drain_timeout=2.5)

        queue_mock.stop.assert_called_once_with(drain_timeout=2.5)

    def test_get_stats_forwards_to_queue(self, pusher):
        queue_mock = MagicMock()
        queue_mock.get_stats.return_value = {
            "enqueued_total": 3,
            "dropped_total": 1,
            "delivered_total": 2,
            "failed_total": 0,
            "retry_total": 1,
            "queue_size": 0,
            "worker_count": 2,
            "workers_alive": 2,
            "started": 1,
        }
        pusher._delivery_queue = queue_mock

        assert pusher.get_stats()["enqueued_total"] == 3
        assert pusher.stats["retry_total"] == 1

    def test_get_stats_when_disabled_returns_zeroes(self, disabled_pusher):
        stats = disabled_pusher.get_stats()

        assert stats["enqueued_total"] == 0
        assert stats["dropped_total"] == 0
        assert stats["delivered_total"] == 0
        assert stats["failed_total"] == 0
        assert stats["retry_total"] == 0
        assert stats["queue_size"] == 0
        assert stats["worker_count"] == 0
        assert stats["workers_alive"] == 0
        assert stats["started"] == 0


# ---------------------------------------------------------------------------
# Confidence Rounding
# ---------------------------------------------------------------------------

class TestConfidenceRounding:

    def test_confidence_rounded_to_4_decimals(self, pusher):
        """Confidence wird auf 4 Nachkommastellen gerundet."""
        pusher._send_envelope = MagicMock()
        pusher.push_mood_changed("focus", 0.123456789)
        call_args = pusher._send_envelope.call_args[0]
        assert call_args[1]["confidence"] == 0.1235


# ---------------------------------------------------------------------------
# HTTP Request Format
# ---------------------------------------------------------------------------

class TestHttpRequest:

    @patch("copilot_core.webhook_pusher.urllib.request.urlopen")
    @patch("copilot_core.webhook_pusher.urllib.request.Request")
    def test_do_post_request_format(self, mock_request_cls, mock_urlopen, pusher):
        """_do_post erstellt korrekte HTTP Request mit Auth-Headern."""
        envelope = {"type": "mood_changed", "data": {"mood": "relax"}}
        mock_req = MagicMock()
        mock_request_cls.return_value = mock_req
        mock_urlopen.return_value.__enter__ = MagicMock(
            return_value=MagicMock(status=200)
        )
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        pusher._do_post(envelope)

        mock_request_cls.assert_called_once()
        call_kwargs = mock_request_cls.call_args
        assert call_kwargs[1]["method"] == "POST"
        body = json.loads(call_kwargs[1]["data"].decode("utf-8"))
        assert body["type"] == "mood_changed"
        mock_req.add_header.assert_any_call("X-Auth-Token", "secret-token")
        mock_req.add_header.assert_any_call("Authorization", "Bearer secret-token")
        assert mock_req.add_header.call_count == 2

    @patch("copilot_core.webhook_pusher.urllib.request.urlopen")
    @patch("copilot_core.webhook_pusher.urllib.request.Request")
    def test_do_post_no_token_header_when_empty(self, mock_request_cls, mock_urlopen):
        """Kein Token-Header wenn webhook_token leer."""
        p = WebhookPusher("http://example.com/hook", "")
        mock_req = MagicMock()
        mock_request_cls.return_value = mock_req
        mock_urlopen.return_value.__enter__ = MagicMock(
            return_value=MagicMock(status=200)
        )
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        p._do_post({"type": "test", "data": {}})
        mock_req.add_header.assert_not_called()
