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
from copilot_core.voice import runtime_access as voice_runtime_access  # noqa: E402


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
    assert payload["error"] == "service_unavailable"
    assert payload["code"] == "backend_missing"
    assert payload["backend"] == "whisper"
    assert "unavailable" in payload["message"].lower()


def test_voice_synthesize_route_returns_audio_path(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    def _test_tts_engine():
        from copilot_core.voice.tts_piper import PiperTTS, TTSConfig
        engine = PiperTTS(TTSConfig(output_dir=str(tmp_path)))
        monkeypatch.setattr(engine, "_check_backend", lambda: True)
        return engine

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


def test_voice_status_exposes_shared_runtime_truth(monkeypatch):
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
        default_language = "de"

    monkeypatch.setattr(voice_api, "_get_intent_handler", lambda: _DummyHandler())
    monkeypatch.setattr(voice_api, "_get_context_builder", lambda: object())
    monkeypatch.setattr(voice_api, "_get_proactive_hints", lambda: _DummyHints())
    monkeypatch.setattr(
        voice_api,
        "_get_voice_health_block",
        lambda: {
            "can_transcribe": True,
            "can_synthesize": True,
            "can_speak": True,
            "can_dialog": True,
            "available_backends": [
                {"type": "stt", "backend": "whisper", "status": "available"},
                {"type": "tts", "backend": "piper", "status": "available"},
            ],
            "runtime": {
                "stt": {
                    "available": True,
                    "engine": "whisper",
                    "model": "base",
                    "default_language": "de",
                    "available_backends": ["whisper"],
                },
                "tts": {
                    "available": True,
                    "engine": "piper",
                    "voice": "de_DE-thorsten",
                    "available_backends": ["piper"],
                },
                "nlu": {
                    "available": True,
                    "engine": "rule_based",
                    "supported_languages": ["de", "en"],
                },
                "intent_handler": {
                    "available": True,
                    "engine": "voice_handler",
                    "default_language": "de",
                },
            },
        },
    )

    client = _make_app().test_client()
    response = client.get("/api/v1/voice/status")

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["components"]["stt_engine"] == "available"
    assert payload["components"]["tts_engine"] == "available"
    assert payload["components"]["nlu_engine"] == "available"
    assert payload["runtime"]["stt"] == {
        "available": True,
        "engine": "whisper",
        "model": "base",
        "default_language": "de",
        "available_backends": ["whisper"],
    }
    assert payload["runtime"]["tts"] == {
        "available": True,
        "engine": "piper",
        "voice": "de_DE-thorsten",
        "available_backends": ["piper"],
    }
    assert payload["runtime"]["nlu"] == {
        "available": True,
        "engine": "rule_based",
        "supported_languages": ["de", "en"],
    }
    assert payload["runtime"]["intent_handler"] == {
        "available": True,
        "engine": "voice_handler",
        "default_language": "de",
    }
    assert payload["capabilities"] == {
        "can_transcribe": True,
        "can_synthesize": True,
        "can_speak": True,
        "can_dialog": True,
    }


def test_voice_status_capabilities_turn_false_when_backends_missing(monkeypatch):
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
        default_language = "de"

    monkeypatch.setattr(voice_api, "_get_intent_handler", lambda: _DummyHandler())
    monkeypatch.setattr(voice_api, "_get_context_builder", lambda: object())
    monkeypatch.setattr(voice_api, "_get_proactive_hints", lambda: _DummyHints())
    monkeypatch.setattr(
        voice_api,
        "_get_voice_health_block",
        lambda: {
            "can_transcribe": False,
            "can_synthesize": False,
            "can_speak": False,
            "can_dialog": False,
            "available_backends": [],
            "runtime": {
                "stt": {
                    "available": False,
                    "engine": "stub",
                    "available_backends": [],
                },
                "tts": {
                    "available": False,
                    "engine": "stub",
                    "available_backends": [],
                },
                "nlu": {
                    "available": True,
                    "engine": "rule_based",
                    "supported_languages": ["de", "en"],
                },
                "intent_handler": {
                    "available": True,
                    "engine": "voice_handler",
                    "default_language": "de",
                },
            },
        },
    )

    client = _make_app().test_client()
    response = client.get("/api/v1/voice/status")

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["components"]["stt_engine"] == "unavailable"
    assert payload["components"]["tts_engine"] == "unavailable"
    assert payload["components"]["nlu_engine"] == "available"
    assert payload["runtime"]["intent_handler"] == {
        "available": True,
        "engine": "voice_handler",
        "default_language": "de",
    }
    assert payload["capabilities"] == {
        "can_transcribe": False,
        "can_synthesize": False,
        "can_speak": False,
        "can_dialog": False,
    }


def test_voice_status_stays_truthful_when_proactive_hints_are_unavailable(monkeypatch):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    class _DummyHandler:
        mood_engine = object()
        habitus_service = None
        default_language = "de"

    monkeypatch.setattr(voice_api, "_get_intent_handler", lambda: _DummyHandler())
    monkeypatch.setattr(voice_api, "_get_context_builder", lambda: object())
    monkeypatch.setattr(voice_api, "_get_proactive_hints", lambda: (_ for _ in ()).throw(RuntimeError("hints offline")))
    monkeypatch.setattr(
        voice_api,
        "_get_voice_health_block",
        lambda: {
            "can_transcribe": False,
            "can_synthesize": False,
            "can_speak": False,
            "can_dialog": False,
            "available_backends": [],
            "runtime": {
                "stt": {
                    "available": False,
                    "engine": "stub",
                    "available_backends": [],
                },
                "tts": {
                    "available": False,
                    "engine": "stub",
                    "available_backends": [],
                },
                "nlu": {
                    "available": True,
                    "engine": "rule_based",
                    "supported_languages": ["de", "en"],
                },
                "intent_handler": {
                    "available": True,
                    "engine": "voice_handler",
                    "default_language": "de",
                },
            },
        },
    )

    client = _make_app().test_client()
    response = client.get("/api/v1/voice/status")

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["components"]["proactive_hints"] == "unavailable"
    assert payload["config"] == {
        "default_language": "de",
        "supported_languages": ["de", "en"],
        "hint_cooldown_seconds": 300,
        "max_hints_per_hour": 6,
        "min_priority": "low",
    }
    assert payload["runtime"]["intent_handler"] == {
        "available": True,
        "engine": "voice_handler",
        "default_language": "de",
    }
    assert payload["capabilities"] == {
        "can_transcribe": False,
        "can_synthesize": False,
        "can_speak": False,
        "can_dialog": False,
    }


def test_voice_status_prefers_injected_runtime_seam(monkeypatch):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    class _DummyHintsConfig:
        hint_cooldown_seconds = 300
        max_hints_per_hour = 6

        class _Priority:
            value = "low"

        min_priority = _Priority()

    class _DummyHints:
        config = _DummyHintsConfig()

    class _DummyHandler:
        mood_engine = object()
        habitus_service = object()
        default_language = "de"

    class _InjectedEngine:
        def __init__(self, payload):
            self._payload = payload

        def availability_payload(self):
            return self._payload

    class _InjectedRuntime:
        def get_intent_handler(self):
            return _DummyHandler()

        def get_context_builder(self):
            return object()

        def get_stt_engine(self):
            return _InjectedEngine({
                "available": True,
                "engine": "injected-whisper",
                "available_backends": ["injected-whisper"],
            })

        def get_tts_engine(self):
            return _InjectedEngine({
                "available": True,
                "engine": "injected-piper",
                "available_backends": ["injected-piper"],
            })

        def get_nlu_engine(self):
            return object()

        def get_proactive_hints(self):
            return _DummyHints()

        def get_generated_audio_cache(self):
            return {}

        def cache_generated_audio(self, audio_path):
            return "ignored"

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("fallback voice runtime construction should not run")

    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_intent_handler", _should_not_be_called)
    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_context_builder", _should_not_be_called)
    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_stt_engine", _should_not_be_called)
    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_tts_engine", _should_not_be_called)
    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_nlu_engine", _should_not_be_called)
    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_proactive_hints", _should_not_be_called)

    app = Flask(__name__)
    voice_runtime_access.init_voice_runtime(app, runtime=_InjectedRuntime())
    app.register_blueprint(voice_api.bp)

    response = app.test_client().get("/api/v1/voice/status")

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["runtime"]["stt"]["engine"] == "injected-whisper"
    assert payload["runtime"]["tts"]["engine"] == "injected-piper"
    assert payload["runtime"]["intent_handler"] == {
        "available": True,
        "engine": "voice_handler",
        "default_language": "de",
    }
    assert payload["capabilities"] == {
        "can_transcribe": True,
        "can_synthesize": True,
        "can_speak": True,
        "can_dialog": True,
    }
