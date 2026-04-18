from __future__ import annotations

"""Contract tests for shared voice health block shape."""

import builtins
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.api.voice_discovery import voice_capabilities_module
from copilot_core.voice import voice_health


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
