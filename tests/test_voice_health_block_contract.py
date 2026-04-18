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

    def can_transcribe(self):
        return self.available

    def can_synthesize(self):
        return self.available


def test_empty_voice_health_block_keeps_capability_shape_stable():
    assert voice_health._empty_block() == {
        "can_transcribe": False,
        "can_synthesize": False,
        "can_speak": False,
        "available_backends": [],
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
        "available_backends": [],
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
        "available_backends": [
            {"type": "tts", "backend": "piper", "status": "available"},
        ],
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
        "available_backends": [
            {"type": "stt", "backend": "whisper", "status": "available"},
        ],
    }
