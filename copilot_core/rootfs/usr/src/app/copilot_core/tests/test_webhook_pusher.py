"""Tests fuer den Webhook Pusher.

Testet Envelope-Format, disabled/enabled Zustand, Queue-Integration und HTTP-Format.
"""
from __future__ import annotations

import json
import socket
from unittest.mock import MagicMock, patch

import pytest

from copilot_core.webhook_pusher import WebhookPusher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pusher() -> WebhookPusher:
    # Most unit tests use localhost URLs; the default destination policy blocks
    # private/loopback targets unless explicitly allowed.
    return WebhookPusher(
        "http://localhost:8123/api/webhook/test",
        "secret-token",
        destination_policy=lambda _url: True,
    )


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
# URL Validation / Destination Policy
# ---------------------------------------------------------------------------


class TestUrlValidation:

    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError):
            WebhookPusher("file:///etc/passwd", "token")

    def test_rejects_ftp_scheme(self):
        with pytest.raises(ValueError):
            WebhookPusher("ftp://example.test/hook", "token")

    def test_rejects_credentials_in_url(self):
        with pytest.raises(ValueError):
            WebhookPusher("http://user:pass@example.test/hook", "token")

    def test_rejects_fragment_in_url(self):
        with pytest.raises(ValueError):
            WebhookPusher("http://example.test/hook#frag", "token")

    def test_destination_policy_can_block_url(self):
        def deny_all(url: str) -> bool:
            assert url.startswith("http")
            return False

        with pytest.raises(ValueError):
            WebhookPusher("http://example.test/hook", "token", destination_policy=deny_all)

    def test_default_destination_policy_blocks_loopback_by_default(self):
        with pytest.raises(ValueError):
            WebhookPusher("http://127.0.0.1:8123/api/webhook/test", "token")

    def test_default_destination_policy_allows_loopback_when_allow_private_env_set(
        self, monkeypatch
    ):
        monkeypatch.setenv("PILOTSUITE_WEBHOOK_DESTINATION_ALLOW_PRIVATE", "true")
        p = WebhookPusher("http://127.0.0.1:8123/api/webhook/test", "token")
        assert p.enabled is True

    def test_default_destination_policy_dns_resolve_blocks_private_when_enabled(
        self, monkeypatch
    ):
        monkeypatch.setenv("PILOTSUITE_WEBHOOK_DESTINATION_RESOLVE_DNS", "true")

        with patch("copilot_core.webhook_destination_policy.socket.getaddrinfo") as mock_getaddr:
            mock_getaddr.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 0)),
            ]
            with pytest.raises(ValueError):
                WebhookPusher("http://example.test/hook", "token")

    def test_default_destination_policy_dns_resolve_allows_public_when_enabled(
        self, monkeypatch
    ):
        monkeypatch.setenv("PILOTSUITE_WEBHOOK_DESTINATION_RESOLVE_DNS", "true")

        with patch("copilot_core.webhook_destination_policy.socket.getaddrinfo") as mock_getaddr:
            mock_getaddr.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
            ]
            p = WebhookPusher("http://example.test/hook", "token")
            assert p.enabled is True


# ---------------------------------------------------------------------------
# Envelope Format
# ---------------------------------------------------------------------------


class TestEnvelopeFormat:

    def test_mood_changed_envelope(self, pusher):
        """push_mood_changed sendet korrektes Envelope-Format."""
        pusher._send_envelope = MagicMock()
        pusher.push_mood_changed("relax", 0.85)
        pusher._send_envelope.assert_called_once_with(
            "mood",
            {"mood": "relax", "confidence": 0.85},
        )

    def test_neuron_update_envelope(self, pusher):
        """push_neuron_update sendet korrektes Envelope-Format."""
        pusher._send_envelope = MagicMock()
        result = {"dominant_mood": "focus", "confidence": 0.72}
        pusher.push_neuron_update(result)
        pusher._send_envelope.assert_called_once_with("neuron", result)

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
            {"type": "mood", "data": {"mood": "relax", "confidence": 0.5}}
        )

    def test_destination_caps_forwarded_to_queue(self, monkeypatch):
        captured = {}

        class _DummyQueue:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def enqueue(self, _envelope):
                return True

            def get_stats(self):  # pragma: no cover - not used in this test
                return {
                    "enqueued_total": 0,
                    "dropped_total": 0,
                    "delivered_total": 0,
                    "failed_total": 0,
                    "retry_total": 0,
                    "deadline_exceeded_total": 0,
                    "rate_limited_total": 0,
                    "destination_concurrency_wait_total": 0,
                    "destination_concurrency_timeout_total": 0,
                    "queue_size": 0,
                    "worker_count": 1,
                    "workers_alive": 1,
                    "started": 1,
                }

            def stop(self, drain_timeout=None):  # pragma: no cover - not used
                return None

        monkeypatch.setattr("copilot_core.webhook_pusher.WebhookDeliveryQueue", _DummyQueue)

        p = WebhookPusher(
            "http://example.test/hook",
            "token",
            destination_max_concurrency=3,
            destination_rate_limit_per_second=5.0,
            destination_rate_limit_burst=10,
            destination_policy=lambda _url: True,
        )

        assert p.enabled is True
        assert captured["destination_max_concurrency"] == 3
        assert captured["destination_rate_limit_per_second"] == 5.0
        assert captured["destination_rate_limit_burst"] == 10

    def test_destination_caps_default_values_when_unspecified(self, monkeypatch):
        captured = {}

        class _DummyQueue:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def enqueue(self, _envelope):
                return True

            def get_stats(self):  # pragma: no cover - not used in this test
                return {
                    "enqueued_total": 0,
                    "dropped_total": 0,
                    "delivered_total": 0,
                    "failed_total": 0,
                    "retry_total": 0,
                    "deadline_exceeded_total": 0,
                    "rate_limited_total": 0,
                    "destination_concurrency_wait_total": 0,
                    "destination_concurrency_timeout_total": 0,
                    "queue_size": 0,
                    "worker_count": 1,
                    "workers_alive": 1,
                    "started": 1,
                }

            def stop(self, drain_timeout=None):  # pragma: no cover - not used
                return None

        monkeypatch.setattr("copilot_core.webhook_pusher.WebhookDeliveryQueue", _DummyQueue)

        p = WebhookPusher(
            "http://example.test/hook",
            "token",
            destination_policy=lambda _url: True,
        )

        assert p.enabled is True
        assert captured["destination_max_concurrency"] is None
        assert captured["destination_rate_limit_per_second"] is None
        assert captured["destination_rate_limit_burst"] == 1

    def test_payload_oversize_is_dropped_before_enqueue(self):
        p = WebhookPusher("http://example.test/hook", "token", max_payload_bytes=64)
        queue_mock = MagicMock()
        queue_mock.enqueue.return_value = True
        queue_mock.get_stats.return_value = {
            "enqueued_total": 0,
            "dropped_total": 0,
            "delivered_total": 0,
            "failed_total": 0,
            "retry_total": 0,
            "deadline_exceeded_total": 0,
            "rate_limited_total": 0,
            "destination_concurrency_wait_total": 0,
            "destination_concurrency_timeout_total": 0,
            "queue_size": 0,
            "worker_count": 1,
            "workers_alive": 1,
            "started": 1,
        }
        p._delivery_queue = queue_mock

        p.push_suggestion({"blob": "x" * 256})

        queue_mock.enqueue.assert_not_called()
        stats = p.get_stats()
        assert stats["payload_oversize_total"] == 1

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
            "deadline_exceeded_total": 0,
            "rate_limited_total": 0,
            "destination_concurrency_wait_total": 0,
            "destination_concurrency_timeout_total": 0,
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
        assert stats["deadline_exceeded_total"] == 0
        assert stats["rate_limited_total"] == 0
        assert stats["destination_concurrency_wait_total"] == 0
        assert stats["destination_concurrency_timeout_total"] == 0
        assert stats["payload_oversize_total"] == 0
        assert stats["destination_rejected_total"] == 0


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
        envelope = {"type": "mood", "data": {"mood": "relax"}}
        mock_req = MagicMock()
        mock_request_cls.return_value = mock_req
        mock_urlopen.return_value.__enter__ = MagicMock(
            return_value=MagicMock(status=200)
        )
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        pusher._do_post(envelope)

        mock_urlopen.assert_called_once_with(mock_req, timeout=pusher._request_timeout_seconds)
        mock_request_cls.assert_called_once()
        call_kwargs = mock_request_cls.call_args[1]
        assert call_kwargs[1]["method"] == "POST"
        body = json.loads(call_kwargs[1]["data"].decode("utf-8"))
        assert body["type"] == "mood"
        mock_req.add_header.assert_any_call("X-Auth-Token", "secret-token")
        mock_req.add_header.assert_any_call("Authorization", "Bearer secret-token")
        assert mock_req.add_header.call_count == 2

    @patch("copilot_core.webhook_pusher.urllib.request.urlopen")
    @patch("copilot_core.webhook_pusher.urllib.request.Request")
    @patch("copilot_core.webhook_pusher.uuid.uuid4")
    @patch("copilot_core.webhook_pusher.time.time")
    def test_do_post_request_format_with_signing(
        self,
        mock_time,
        mock_uuid4,
        mock_request_cls,
        mock_urlopen,
    ):
        """Signing-Signale werden als Replay-Defense korrekt gesetzt."""
        envelope = {"type": "mood", "data": {"mood": "relax"}}
        mock_req = MagicMock()
        mock_request_cls.return_value = mock_req
        mock_urlopen.return_value.__enter__ = MagicMock(
            return_value=MagicMock(status=200)
        )
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        mock_time.return_value = 1710000000.0
        mock_uuid4.return_value.hex = "7c9f86d4e0d948f2a9d4a4b1f7b1f2f1"

        p = WebhookPusher(
            "http://example.com/hook",
            "secret-token",
            webhook_signing_secret="shared-secret",
        )

        p._do_post(envelope)

        mock_urlopen.assert_called_once_with(mock_req, timeout=p._request_timeout_seconds)
        mock_request_cls.assert_called_once()
        call_kwargs = mock_request_cls.call_args[1]
        body = call_kwargs[1]["data"]
        timestamp = "1710000000"
        expected_signature = WebhookPusher._build_signature(
            "shared-secret",
            body=body,
            timestamp=timestamp,
            nonce="7c9f86d4e0d948f2a9d4a4b1f7b1f2f1",
        )

        mock_req.add_header.assert_any_call("X-Webhook-Timestamp", timestamp)
        mock_req.add_header.assert_any_call(
            "X-Webhook-Nonce",
            "7c9f86d4e0d948f2a9d4a4b1f7b1f2f1",
        )
        mock_req.add_header.assert_any_call("X-Webhook-Signature", expected_signature)

    @patch("copilot_core.webhook_pusher.urllib.request.urlopen")
    @patch("copilot_core.webhook_pusher.urllib.request.Request")
    def test_do_post_no_token_or_signing_headers_when_secret_missing(
        self,
        mock_request_cls,
        mock_urlopen,
    ):
        """Keine Auth-/Signing-Header wenn weder Token noch Signing-Secret gesetzt."""
        p = WebhookPusher("http://example.com/hook", "")
        mock_req = MagicMock()
        mock_request_cls.return_value = mock_req
        mock_urlopen.return_value.__enter__ = MagicMock(
            return_value=MagicMock(status=200)
        )
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        p._do_post({"type": "test", "data": {}})
        mock_req.add_header.assert_not_called()
