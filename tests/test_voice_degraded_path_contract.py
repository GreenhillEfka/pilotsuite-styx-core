"""Voice API Degraded-Path Contract Tests.

Verifies that the voice API returns stable 503 responses when Whisper STT or
Piper TTS backends are unavailable — not generic 500 errors or false-positive
200s with placeholder data.

Contract:
- STT unavailable (returns None) → 503 with {"status": "error", "message": "Voice transcription unavailable"}
- TTS unavailable (returns None)   → 503 with {"status": "error", "message": "Voice synthesis unavailable"}
- Engine raises exception → 500 with {"status": "error"} (code bug, not degraded path)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.api.v1 import voice as voice_api  # noqa: E402


def _make_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(voice_api.bp)
    return app


def _patch_auth():
    """Bypass token validation for tests."""
    voice_api._validate_token = lambda request: True


class TestSTTDegradedPath:
    """STT degraded path: Whisper backend unavailable."""

    def test_transcribe_returns_503_when_engine_returns_none(self, monkeypatch):
        """
        When _get_stt_engine() returns an engine whose transcribe() returns None
        (meaning backend unavailable), the endpoint MUST return 503.
        """
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

        def _fake_stt_engine():
            engine = MagicMock()
            engine.transcribe.return_value = None  # Backend unavailable
            return engine

        monkeypatch.setattr(voice_api, "_get_stt_engine", _fake_stt_engine)

        client = _make_app().test_client()
        response = client.post(
            "/api/v1/voice/transcribe",
            json={"audio_path": "/tmp/test.wav", "language": "de"},
        )

        assert response.status_code == 503, (
            f"Expected 503 when STT unavailable, got {response.status_code}. "
            f"Body: {response.get_data(as_text=True)}"
        )
        data = response.get_json()
        assert data["status"] == "error"
        assert "unavailable" in data["message"].lower()

    def test_transcribe_returns_500_when_engine_raises(self, monkeypatch):
        """
        When the STT engine raises an exception (code bug), endpoint returns 500.
        A 500 is NOT a stable degraded path — it means the code needs fixing.
        """
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

        def _fake_stt_engine():
            engine = MagicMock()
            engine.transcribe.side_effect = RuntimeError("Whisper crashed")
            return engine

        monkeypatch.setattr(voice_api, "_get_stt_engine", _fake_stt_engine)

        client = _make_app().test_client()
        response = client.post(
            "/api/v1/voice/transcribe",
            json={"audio_path": "/tmp/test.wav"},
        )

        assert response.status_code == 500, f"Expected 500 on engine crash, got {response.status_code}"
        data = response.get_json()
        assert data["status"] == "error"


class TestTTSDegradedPath:
    """TTS degraded path: Piper backend unavailable."""

    def test_synthesize_returns_503_when_engine_returns_none(self, monkeypatch):
        """
        When _get_tts_engine() returns an engine whose synthesize() returns None
        (meaning backend unavailable), the endpoint MUST return 503.
        """
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

        def _fake_tts_engine():
            engine = MagicMock()
            engine.synthesize.return_value = None  # Backend unavailable
            return engine

        monkeypatch.setattr(voice_api, "_get_tts_engine", _fake_tts_engine)

        client = _make_app().test_client()
        response = client.post(
            "/api/v1/voice/synthesize",
            json={"text": "Hello world", "voice": "de_DE-thorsten"},
        )

        assert response.status_code == 503, (
            f"Expected 503 when TTS unavailable, got {response.status_code}. "
            f"Body: {response.get_data(as_text=True)}"
        )
        data = response.get_json()
        assert data["status"] == "error"
        assert "unavailable" in data["message"].lower()

    def test_synthesize_returns_500_when_engine_raises(self, monkeypatch):
        """
        When the TTS engine raises an exception (code bug), endpoint returns 500.
        """
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

        def _fake_tts_engine():
            engine = MagicMock()
            engine.synthesize.side_effect = RuntimeError("Piper crashed")
            return engine

        monkeypatch.setattr(voice_api, "_get_tts_engine", _fake_tts_engine)

        client = _make_app().test_client()
        response = client.post(
            "/api/v1/voice/synthesize",
            json={"text": "Hello world"},
        )

        assert response.status_code == 500, f"Expected 500 on engine crash, got {response.status_code}"
        data = response.get_json()
        assert data["status"] == "error"