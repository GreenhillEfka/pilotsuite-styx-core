"""Tests for Styx Voice API (styx_voice.py).

Tests the STT and TTS endpoints:
  - POST /api/v1/styx/stt     (speech-to-text)
  - POST /api/v1/styx/tts     (text-to-speech)
  - GET  /api/v1/styx/voice/status (health check)

Uses a real Flask test client with mocked external services.
"""

import io
import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask


def _make_app():
    """Create a Flask app with the styx_voice blueprint and auth bypassed."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    from copilot_core.api.v1.styx_voice import styx_voice_bp
    app.register_blueprint(styx_voice_bp)
    return app


@pytest.fixture
def client():
    """Flask test client with auth bypassed."""
    with patch("copilot_core.api.v1.styx_voice.validate_token", return_value=True):
        app = _make_app()
        with app.test_client() as c:
            yield c


@pytest.fixture
def unauth_client():
    """Flask test client with auth denied."""
    with patch("copilot_core.api.v1.styx_voice.validate_token", return_value=False):
        app = _make_app()
        with app.test_client() as c:
            yield c


# ── Auth Tests ────────────────────────────────────────────────────────

class TestVoiceAuth:
    def test_stt_requires_auth(self, unauth_client):
        resp = unauth_client.post("/api/v1/styx/stt", data=b"audio")
        assert resp.status_code == 401

    def test_tts_requires_auth(self, unauth_client):
        resp = unauth_client.post(
            "/api/v1/styx/tts",
            data=json.dumps({"text": "hello"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_status_requires_auth(self, unauth_client):
        resp = unauth_client.get("/api/v1/styx/voice/status")
        assert resp.status_code == 401


# ── STT Tests ─────────────────────────────────────────────────────────

class TestSTT:
    def test_stt_no_audio(self, client):
        resp = client.post("/api/v1/styx/stt")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["ok"] is False
        assert "audio" in data["error"].lower()

    def test_stt_with_file_upload(self, client):
        """STT with multipart file upload via Ollama Whisper."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "Hallo Welt"}

        # requests is imported inside the endpoint function as http_requests
        with patch("requests.post", return_value=mock_resp):
            data = {"audio": (io.BytesIO(b"fake-wav-data"), "test.wav")}
            resp = client.post(
                "/api/v1/styx/stt",
                data=data,
                content_type="multipart/form-data",
            )
            assert resp.status_code == 200
            result = json.loads(resp.data)
            assert result["ok"] is True
            assert result["text"] == "Hallo Welt"
            assert result["language"] == "de"

    def test_stt_with_raw_body(self, client):
        """STT with raw audio bytes in request body."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "Test Ergebnis"}

        with patch("requests.post", return_value=mock_resp):
            resp = client.post(
                "/api/v1/styx/stt?language=en",
                data=b"raw-audio-bytes",
                content_type="application/octet-stream",
            )
            assert resp.status_code == 200
            result = json.loads(resp.data)
            assert result["ok"] is True
            assert result["text"] == "Test Ergebnis"
            assert result["language"] == "en"

    def test_stt_ollama_down_cloud_fallback(self, client):
        """When Ollama fails, fall back to cloud endpoint."""
        mock_ollama_fail = Mock(side_effect=ConnectionError("refused"))
        mock_cloud_resp = Mock()
        mock_cloud_resp.status_code = 200
        mock_cloud_resp.json.return_value = {"text": "Cloud result"}

        def mock_post(url, **kwargs):
            if "localhost" in url or "127.0.0.1" in url:
                raise ConnectionError("refused")
            return mock_cloud_resp

        with patch("requests.post", side_effect=mock_post):
            with patch.dict(os.environ, {
                "CLOUD_API_URL": "https://api.openai.com/v1/chat/completions",
                "CLOUD_API_KEY": "sk-test-key",
            }):
                resp = client.post(
                    "/api/v1/styx/stt",
                    data=b"audio-data",
                    content_type="application/octet-stream",
                )
                assert resp.status_code == 200
                result = json.loads(resp.data)
                assert result["ok"] is True
                assert result["text"] == "Cloud result"

    def test_stt_all_providers_down(self, client):
        """When all STT providers fail, return 503."""
        with patch("requests.post", side_effect=ConnectionError("all down")):
            resp = client.post(
                "/api/v1/styx/stt",
                data=b"audio-data",
                content_type="application/octet-stream",
            )
            assert resp.status_code == 503
            result = json.loads(resp.data)
            assert result["ok"] is False


# ── TTS Tests ─────────────────────────────────────────────────────────

class TestTTS:
    def test_tts_no_text(self, client):
        resp = client.post(
            "/api/v1/styx/tts",
            data=json.dumps({"text": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["ok"] is False

    def test_tts_missing_body(self, client):
        resp = client.post(
            "/api/v1/styx/tts",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_tts_edge_tts_success(self, client):
        """TTS generates audio via edge-tts."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        def mock_run(cmd, **kwargs):
            # Write fake MP3 data to the output file
            for i, arg in enumerate(cmd):
                if arg == "--write-media" and i + 1 < len(cmd):
                    with open(cmd[i + 1], "wb") as f:
                        f.write(b"fake-mp3-data-content")
            return mock_result

        with patch("copilot_core.api.v1.styx_voice.subprocess.run", side_effect=mock_run):
            resp = client.post(
                "/api/v1/styx/tts",
                data=json.dumps({"text": "Hallo Welt", "language": "de"}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            assert resp.content_type == "audio/mpeg"
            assert len(resp.data) > 0

    def test_tts_edge_tts_not_installed(self, client):
        """TTS returns 503 when edge-tts is not installed."""
        with patch(
            "copilot_core.api.v1.styx_voice.subprocess.run",
            side_effect=FileNotFoundError("edge-tts not found"),
        ):
            resp = client.post(
                "/api/v1/styx/tts",
                data=json.dumps({"text": "Test"}),
                content_type="application/json",
            )
            assert resp.status_code == 503
            data = json.loads(resp.data)
            assert "not installed" in data["error"]

    def test_tts_edge_tts_timeout(self, client):
        """TTS returns 504 on timeout."""
        import subprocess
        with patch(
            "copilot_core.api.v1.styx_voice.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="edge-tts", timeout=30),
        ):
            resp = client.post(
                "/api/v1/styx/tts",
                data=json.dumps({"text": "Test"}),
                content_type="application/json",
            )
            assert resp.status_code == 504

    def test_tts_text_truncation(self, client):
        """Text over 5000 chars is truncated."""
        long_text = "A" * 6000
        mock_result = Mock()
        mock_result.returncode = 0

        received_text = []

        def mock_run(cmd, **kwargs):
            for i, arg in enumerate(cmd):
                if arg == "--text" and i + 1 < len(cmd):
                    received_text.append(cmd[i + 1])
                if arg == "--write-media" and i + 1 < len(cmd):
                    with open(cmd[i + 1], "wb") as f:
                        f.write(b"mp3-data")
            return mock_result

        with patch("copilot_core.api.v1.styx_voice.subprocess.run", side_effect=mock_run):
            resp = client.post(
                "/api/v1/styx/tts",
                data=json.dumps({"text": long_text}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            assert len(received_text[0]) == 5000

    def test_tts_unknown_engine(self, client):
        """Unknown TTS engine returns 400."""
        with patch.dict(os.environ, {"STYX_TTS_ENGINE": "unknown"}):
            # Need to reload the module to pick up the new env var
            # Instead, patch the module-level variable
            with patch("copilot_core.api.v1.styx_voice.TTS_ENGINE", "unknown"):
                resp = client.post(
                    "/api/v1/styx/tts",
                    data=json.dumps({"text": "Test"}),
                    content_type="application/json",
                )
                assert resp.status_code == 400


# ── Voice Status Tests ────────────────────────────────────────────────

class TestVoiceStatus:
    def test_status_ok(self, client):
        """Status endpoint returns STT and TTS availability."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "whisper:latest"}]
        }

        with patch("requests.get", return_value=mock_resp):
            with patch("shutil.which", return_value="/usr/bin/edge-tts"):
                resp = client.get("/api/v1/styx/voice/status")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert data["stt"]["available"] is True
                assert data["tts"]["available"] is True

    def test_status_no_whisper(self, client):
        """Status when Whisper model is not available."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "qwen3:0.6b"}]}

        with patch("requests.get", return_value=mock_resp):
            with patch("shutil.which", return_value="/usr/bin/edge-tts"):
                resp = client.get("/api/v1/styx/voice/status")
                data = json.loads(resp.data)
                assert data["stt"]["available"] is False
                assert data["tts"]["available"] is True

    def test_status_no_edge_tts(self, client):
        """Status when edge-tts is not installed."""
        with patch("requests.get", side_effect=ConnectionError("down")):
            with patch("shutil.which", return_value=None):
                resp = client.get("/api/v1/styx/voice/status")
                data = json.loads(resp.data)
                assert data["stt"]["available"] is False
                assert data["tts"]["available"] is False
