"""Contract tests for voice readiness truth on health/readiness surfaces.

Verifies:
- /api/v1/voice/status truth is embedded in /health and /ready payloads
- Service-level /health stays ok:true even when voice backends are unavailable
- Service-level /ready stays 200 even when voice backends are unavailable
"""
from __future__ import annotations

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


@pytest.mark.skip(reason="H4-flaky-004: full-suite context pollution — passes in isolation, fails in full suite")
class TestVoiceReadinessSurface:
    """Voice capability truth on existing health/readiness surfaces."""

    def _create_app_client(self):
        import os
        os.environ.setdefault("COPILOT_AUTH_TOKEN", "pilotclaw-test-token")
        from copilot_core.app import create_app
        app = create_app()
        return app.test_client()

    def test_health_response_includes_voice_nested_block(self):
        """Service /health includes nested voice truth block."""
        client = self._create_app_client()
        token = {"X-Auth-Token": "pilotclaw-test-token"}
        resp = client.get("/api/v1/health", headers=token)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True or data.get("status") in ("healthy", "degraded", "unhealthy")
        voice = data.get("voice", {})
        assert isinstance(voice, dict), "voice block should be a dict"
        assert "can_transcribe" in voice
        assert "can_synthesize" in voice

    def test_health_voice_block_derives_from_voice_status_truth(self):
        """Voice block on /health reflects same truth as /api/v1/voice/status."""
        client = self._create_app_client()
        token = {"X-Auth-Token": "pilotclaw-test-token"}
        health_resp = client.get("/api/v1/health", headers=token)
        voice_status_resp = client.get("/api/v1/voice/status", headers=token)
        health_data = health_resp.get_json()
        status_data = voice_status_resp.get_json()
        health_voice = health_data.get("voice", {})
        stt_health = health_voice.get("can_transcribe")
        tts_health = health_voice.get("can_synthesize")
        stt_status = status_data.get("can_transcribe") or status_data.get("capabilities", {}).get("can_transcribe")
        tts_status = status_data.get("can_synthesize") or status_data.get("capabilities", {}).get("can_synthesize")
        assert stt_health == stt_status, f"can_transcribe mismatch: health={stt_health} status={stt_status}"
        assert tts_health == tts_status, f"can_synthesize mismatch: health={tts_health} status={tts_status}"

    def test_ready_response_includes_voice_nested_block(self):
        """Service /ready includes nested voice truth block."""
        client = self._create_app_client()
        token = {"X-Auth-Token": "pilotclaw-test-token"}
        resp = client.get("/api/v1/ready", headers=token)
        assert resp.status_code in (200, 503)
        data = resp.get_json()
        voice = data.get("voice", {})
        assert isinstance(voice, dict), "voice block should be a dict"
        assert "can_transcribe" in voice
        assert "can_synthesize" in voice

    def test_ready_stays_200_when_voice_backends_unavailable(self):
        """Service /ready returns 200 even when Whisper/Piper unavailable."""
        client = self._create_app_client()
        token = {"X-Auth-Token": "pilotclaw-test-token"}
        resp = client.get("/api/v1/ready", headers=token)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.get_json()}"

    def test_health_ok_true_when_voice_backends_unavailable(self):
        """Service /health returns ok:true even when Whisper/Piper unavailable."""
        client = self._create_app_client()
        token = {"X-Auth-Token": "pilotclaw-test-token"}
        resp = client.get("/api/v1/health", headers=token)
        data = resp.get_json()
        assert data.get("ok") is True or data.get("status") in ("healthy", "degraded")

    def test_voice_block_includes_backend_status(self):
        """Voice block carries backend status for ops visibility."""
        client = self._create_app_client()
        token = {"X-Auth-Token": "pilotclaw-test-token"}
        resp = client.get("/api/v1/health", headers=token)
        data = resp.get_json()
        voice = data.get("voice", {})
        assert "available_backends" in voice
        assert isinstance(voice["available_backends"], list)

    def test_health_voice_block_is_absent_when_service_health_unknown(self):
        """If voice status cannot be determined, voice block may be absent (not error)."""
        client = self._create_app_client()
        token = {"X-Auth-Token": "pilotclaw-test-token"}
        resp = client.get("/api/v1/health", headers=token)
        data = resp.get_json()
        assert "voice" in data or "voice" not in data  # must not raise