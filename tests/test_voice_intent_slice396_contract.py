"""Voice Intent Contract Tests — Slice 396: user_preferences replay on alias-equivalent double zone-name seam."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock security module BEFORE importing voice module
mock_security = MagicMock()
mock_security.require_token = lambda f: f
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import voice as voice_api


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(voice_api.bp)
    return app


# ── Slice 396 tests ──


def test_voice_intent_double_context_zone_name_alias_equivalent_same_zone_preserves_user_preferences_replay(monkeypatch):
    """Alias (Wohnzimmer) + canonical (wohnzimmer) double zone-name preserves user_preferences replay."""
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    app = _make_app()
    client = app.test_client()
    response = client.post("/api/v1/voice/intent", json={
        "text": "Mach das Licht an",
        "context": {
            "zone_name": "Wohnzimmer",
            "zone": {"zone_name": "wohnzimmer"},
            "user_preferences": {"preferred_language": "de", "tts_voice": "warm"},
        },
    })

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    # canonical zone returned
    assert payload["context"]["zone_name"] == "wohnzimmer"
    # user_preferences from body merged into context
    assert payload["context"]["user_preferences"]["tts_voice"] == "warm"
    assert payload["context"]["user_preferences"]["preferred_language"] == "de"
    # zone metadata stable
    assert payload["context"]["zone"]["zone_name"] == "wohnzimmer"
    assert payload["context"]["zone"]["zone_type"] == "living_room"


def test_voice_intent_inverse_double_context_zone_name_alias_equivalent_same_zone_preserves_user_preferences_replay(monkeypatch):
    """Canonical (wohnzimmer) + alias (Wohnzimmer) double zone-name preserves user_preferences replay."""
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    app = _make_app()
    client = app.test_client()
    response = client.post("/api/v1/voice/intent", json={
        "text": "Mach das Licht an",
        "context": {
            "zone_name": "wohnzimmer",
            "zone": {"zone_name": "Wohnzimmer"},
            "user_preferences": {"preferred_language": "de", "tts_voice": "warm"},
        },
    })

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["context"]["zone_name"] == "wohnzimmer"
    assert payload["context"]["user_preferences"]["tts_voice"] == "warm"
    assert payload["context"]["user_preferences"]["preferred_language"] == "de"
    assert payload["context"]["zone"]["zone_name"] == "wohnzimmer"
    assert payload["context"]["zone"]["zone_type"] == "living_room"
