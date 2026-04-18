"""Contract tests for the restored /api/v1/voice/transcribe and /synthesize routes."""
from __future__ import annotations

import sys
from pathlib import Path

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


def test_voice_transcribe_degraded_when_whisper_unavailable(monkeypatch):
    """
    When Whisper is not installed, transcribe endpoint returns 503.
    This is the correct degraded path — not a 200 with fake data.
    """
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    def _fake_stt_engine():
        from copilot_core.voice.stt_whisper import WhisperSTT, STTConfig
        engine = WhisperSTT(STTConfig(model="base", language="de"))
        # Simulate unavailable backend
        engine._check_backend = lambda: False
        engine._unavailable = True
        engine._loaded = False
        return engine

    monkeypatch.setattr(voice_api, "_get_stt_engine", _fake_stt_engine)

    client = _make_app().test_client()
    response = client.post(
        "/api/v1/voice/transcribe",
        json={"audio_path": "dummy.wav", "language": "de"},
    )

    # Correct degraded path: 503 when backend unavailable
    assert response.status_code == 503, response.get_json()
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "unavailable" in payload["message"].lower()


def test_voice_synthesize_route_returns_audio_path(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    def _test_tts_engine():
        from copilot_core.voice.tts_piper import PiperTTS, TTSConfig

        return PiperTTS(TTSConfig(output_dir=str(tmp_path)))

    monkeypatch.setattr(voice_api, "_get_tts_engine", _test_tts_engine)

    client = _make_app().test_client()
    response = client.post(
        "/api/v1/voice/synthesize",
        json={"text": "Hallo Welt", "voice": "de_DE-thorsten"},
    )

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["voice"] == "de_DE-thorsten"
    assert Path(payload["audio_path"]).exists()


def test_voice_status_exposes_stt_tts_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    class _DummyHintsConfig:
        hint_cooldown_seconds = 300
        max_hints_per_hour = 6

        class _Priority:
            value = "medium"

        min_priority = _Priority()

    class _DummyHints:
        config = _DummyHintsConfig()

    class _DummyHandler:
        mood_engine = object()
        habitus_service = None

    monkeypatch.setattr(voice_api, "_get_intent_handler", lambda: _DummyHandler())
    monkeypatch.setattr(voice_api, "_get_context_builder", lambda: object())
    monkeypatch.setattr(voice_api, "_get_proactive_hints", lambda: _DummyHints())

    def _test_stt_engine():
        from copilot_core.voice.stt_whisper import WhisperSTT, STTConfig

        return WhisperSTT(STTConfig(model="base", language="de"))

    def _test_tts_engine():
        from copilot_core.voice.tts_piper import PiperTTS, TTSConfig

        return PiperTTS(TTSConfig(output_dir=str(tmp_path), voice="de_DE-thorsten"))

    monkeypatch.setattr(voice_api, "_get_stt_engine", _test_stt_engine)
    monkeypatch.setattr(voice_api, "_get_tts_engine", _test_tts_engine)

    client = _make_app().test_client()
    response = client.get("/api/v1/voice/status")

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["components"]["stt_engine"] == "available"
    assert payload["components"]["tts_engine"] == "available"
    assert payload["runtime"]["stt"] == {
        "available": True,
        "engine": "whisper",
        "model": "base",
        "default_language": "de",
    }
    assert payload["runtime"]["tts"] == {
        "available": True,
        "engine": "piper",
        "voice": "de_DE-thorsten",
    }
