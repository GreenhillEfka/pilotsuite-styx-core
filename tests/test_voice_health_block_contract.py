from __future__ import annotations

"""Contract tests for shared voice health block shape."""

import builtins
import sys
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.api.voice_discovery import voice_capabilities_module
from copilot_core.voice import voice_health


class _BackendProbe:
    def __init__(self, available: bool):
        self.available = available

    def availability_payload(self):
        return {"available": self.available}

    def is_available(self):
        return self.available


def test_empty_voice_health_block_keeps_capability_shape_stable():
    assert voice_health._empty_block() == {
        "can_transcribe": False,
        "can_synthesize": False,
        "can_speak": False,
        "can_dialog": False,
        "available_backends": [],
        "runtime": {
            "stt": {
                "available": False,
                "engine": "whisper",
                "available_backends": [],
            },
            "tts": {
                "available": False,
                "engine": "piper",
                "available_backends": [],
            },
            "nlu": {
                "available": False,
                "engine": "rule_based",
                "supported_languages": ["de", "en"],
            },
            "intent_handler": {
                "available": False,
                "engine": "voice_handler",
                "default_language": "de",
            },
        },
    }


def test_voice_capabilities_module_fallback_keeps_can_speak_field():
    original_import = builtins.__import__

    def _raising_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "copilot_core.voice.voice_health":
            raise ImportError("simulated missing voice health helper")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=_raising_import):
        payload = voice_capabilities_module()

    assert payload["runtime"] == {
        "can_transcribe": False,
        "can_synthesize": False,
        "can_speak": False,
        "can_dialog": False,
        "available_backends": [],
        "runtime": {
            "stt": {
                "available": False,
                "engine": "whisper",
                "available_backends": [],
            },
            "tts": {
                "available": False,
                "engine": "piper",
                "available_backends": [],
            },
            "nlu": {
                "available": False,
                "engine": "rule_based",
                "supported_languages": ["de", "en"],
            },
            "intent_handler": {
                "available": False,
                "engine": "voice_handler",
                "default_language": "de",
            },
        },
    }


def test_voice_health_block_keeps_tts_truth_when_stt_import_fails(monkeypatch):
    def _fake_import_module(module_path: str):
        if module_path == "copilot_core.voice.stt_whisper":
            raise ImportError("missing whisper")
        if module_path == "copilot_core.voice.tts_piper":
            return types.SimpleNamespace(PiperTTS=lambda: _BackendProbe(True))
        raise AssertionError(f"unexpected module lookup: {module_path}")

    monkeypatch.setattr(voice_health.importlib, "import_module", _fake_import_module)

    assert voice_health.get_voice_health_block() == {
        "can_transcribe": False,
        "can_synthesize": True,
        "can_speak": True,
        "can_dialog": False,
        "available_backends": [
            {"type": "tts", "backend": "piper", "status": "available"},
        ],
        "runtime": {
            "stt": {
                "available": False,
                "engine": "whisper",
                "available_backends": [],
            },
            "tts": {
                "available": True,
                "engine": "piper",
                "available_backends": [],
            },
            "nlu": {
                "available": False,
                "engine": "rule_based",
                "supported_languages": ["de", "en"],
            },
            "intent_handler": {
                "available": False,
                "engine": "voice_handler",
                "default_language": "de",
            },
        },
    }


def test_voice_health_block_keeps_stt_truth_when_tts_import_fails(monkeypatch):
    def _fake_import_module(module_path: str):
        if module_path == "copilot_core.voice.stt_whisper":
            return types.SimpleNamespace(WhisperSTT=lambda: _BackendProbe(True))
        if module_path == "copilot_core.voice.tts_piper":
            raise ImportError("missing piper")
        raise AssertionError(f"unexpected module lookup: {module_path}")

    monkeypatch.setattr(voice_health.importlib, "import_module", _fake_import_module)

    assert voice_health.get_voice_health_block() == {
        "can_transcribe": True,
        "can_synthesize": False,
        "can_speak": False,
        "can_dialog": False,
        "available_backends": [
            {"type": "stt", "backend": "whisper", "status": "available"},
        ],
        "runtime": {
            "stt": {
                "available": True,
                "engine": "whisper",
                "available_backends": [],
            },
            "tts": {
                "available": False,
                "engine": "piper",
                "available_backends": [],
            },
            "nlu": {
                "available": False,
                "engine": "rule_based",
                "supported_languages": ["de", "en"],
            },
            "intent_handler": {
                "available": False,
                "engine": "voice_handler",
                "default_language": "de",
            },
        },
    }


def test_voice_health_block_prefers_current_engine_availability_surface(monkeypatch):
    class _ShippedSttProbe:
        def availability_payload(self):
            return {"available": True, "engine": "whisper"}

    class _ShippedTtsProbe:
        def is_available(self):
            return True

    def _fake_import_module(module_path: str):
        if module_path == "copilot_core.voice.stt_whisper":
            return types.SimpleNamespace(WhisperSTT=lambda: _ShippedSttProbe())
        if module_path == "copilot_core.voice.tts_piper":
            return types.SimpleNamespace(PiperTTS=lambda: _ShippedTtsProbe())
        if module_path == "copilot_core.voice.nlu_engine":
            return types.SimpleNamespace(NLUEngine=lambda: object())
        if module_path == "copilot_core.voice.voice_handler":
            return types.SimpleNamespace(VoiceIntentHandler=lambda: object())
        raise AssertionError(f"unexpected module lookup: {module_path}")

    monkeypatch.setattr(voice_health.importlib, "import_module", _fake_import_module)

    assert voice_health.get_voice_health_block() == {
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
                "available_backends": [],
            },
            "tts": {
                "available": True,
                "engine": "piper",
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
    }


def test_voice_health_block_prefers_injected_runtime_truth_for_dialog_capability(monkeypatch):
    class _AvailableEngine:
        def __init__(self, engine: str | None = None):
            self._engine = engine

        def availability_payload(self):
            payload = {"available": True}
            if self._engine is not None:
                payload["engine"] = self._engine
            return payload

    class _InjectedRuntime:
        def get_stt_engine(self):
            return _AvailableEngine("runtime-whisper")

        def get_tts_engine(self):
            return _AvailableEngine("runtime-piper")

        def get_nlu_engine(self):
            return object()

        def get_intent_handler(self):
            return object()

    monkeypatch.setattr(voice_health, "has_app_context", lambda: True)
    monkeypatch.setattr(voice_health, "get_voice_runtime", lambda: _InjectedRuntime())

    assert voice_health.get_voice_health_block() == {
        "can_transcribe": True,
        "can_synthesize": True,
        "can_speak": True,
        "can_dialog": True,
        "available_backends": [
            {"type": "stt", "backend": "runtime-whisper", "status": "available"},
            {"type": "tts", "backend": "runtime-piper", "status": "available"},
        ],
        "runtime": {
            "stt": {
                "available": True,
                "engine": "runtime-whisper",
                "available_backends": [],
            },
            "tts": {
                "available": True,
                "engine": "runtime-piper",
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
    }
