"""Tests fuer den Webhook Pusher.

Testet Envelope-Format, disabled/enabled Zustand und Push-Methoden.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock

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

    def test_enabled_with_url(self, pusher):
        assert pusher.enabled is True

    def test_disabled_without_url(self, disabled_pusher):
        assert disabled_pusher.enabled is False

    def test_disabled_empty_string(self):
        p = WebhookPusher("", "token")
        assert p.enabled is False


# ---------------------------------------------------------------------------
# Envelope Format
# ---------------------------------------------------------------------------

class TestEnvelopeFormat:

    @patch.object(WebhookPusher, "_do_post")
    def test_mood_changed_envelope(self, mock_post, pusher):
        """push_mood_changed sendet korrektes Envelope-Format."""
        pusher._send_envelope = MagicMock()
        pusher.push_mood_changed("relax", 0.85)
        pusher._send_envelope.assert_called_once_with(
            "mood_changed",
            {"mood": "relax", "confidence": 0.85},
        )

    @patch.object(WebhookPusher, "_do_post")
    def test_neuron_update_envelope(self, mock_post, pusher):
        """push_neuron_update sendet korrektes Envelope-Format."""
        pusher._send_envelope = MagicMock()
        result = {"dominant_mood": "focus", "confidence": 0.72}
        pusher.push_neuron_update(result)
        pusher._send_envelope.assert_called_once_with("neuron_update", result)

    @patch.object(WebhookPusher, "_do_post")
    def test_suggestion_envelope(self, mock_post, pusher):
        """push_suggestion sendet korrektes Envelope-Format."""
        pusher._send_envelope = MagicMock()
        suggestion = {"action": "dim_lights", "reason": "bedtime"}
        pusher.push_suggestion(suggestion)
        pusher._send_envelope.assert_called_once_with("suggestion", suggestion)


# ---------------------------------------------------------------------------
# Disabled Pusher ignoriert Aufrufe
# ---------------------------------------------------------------------------

class TestDisabledPusher:

    @patch("copilot_core.webhook_pusher.threading.Thread")
    def test_no_thread_when_disabled(self, mock_thread, disabled_pusher):
        """Kein Thread wird gestartet wenn Pusher deaktiviert."""
        disabled_pusher.push_mood_changed("relax", 0.5)
        mock_thread.assert_not_called()

    @patch("copilot_core.webhook_pusher.threading.Thread")
    def test_thread_started_when_enabled(self, mock_thread, pusher):
        """Thread wird gestartet wenn Pusher aktiv."""
        mock_instance = MagicMock()
        mock_thread.return_value = mock_instance
        pusher.push_mood_changed("relax", 0.5)
        mock_thread.assert_called_once()
        mock_instance.start.assert_called_once()


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
        """_do_post erstellt korrekte HTTP Request mit Token-Header."""
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
        mock_req.add_header.assert_called_once_with("X-CoPilot-Token", "secret-token")

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
