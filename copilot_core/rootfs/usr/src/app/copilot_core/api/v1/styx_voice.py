"""
Styx Voice API — STT and TTS endpoints for HA integration.

Endpoints:
    POST /api/v1/styx/stt     — Speech-to-text (audio → text)
    POST /api/v1/styx/tts     — Text-to-speech (text → audio)
    GET  /api/v1/styx/voice/status — Voice service health

STT: Uses Whisper via Ollama or configurable external endpoint.
TTS: Uses edge-tts (offline) or configurable external endpoint.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
from typing import Any

from flask import Blueprint, jsonify, request, send_file

from copilot_core.api.security import validate_token

_LOGGER = logging.getLogger(__name__)

styx_voice_bp = Blueprint("styx_voice", __name__, url_prefix="/api/v1/styx")

# ── Configuration ────────────────────────────────────────────────────

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
STT_MODEL = os.environ.get("STYX_STT_MODEL", "whisper")
TTS_VOICE = os.environ.get("STYX_TTS_VOICE", "de-DE-ConradNeural")
TTS_ENGINE = os.environ.get("STYX_TTS_ENGINE", "edge-tts")  # edge-tts or piper


@styx_voice_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


# ═══════════════════════════════════════════════════════════════════════
# POST /api/v1/styx/stt — Speech-to-Text
# ═══════════════════════════════════════════════════════════════════════

@styx_voice_bp.route("/stt", methods=["POST"])
def speech_to_text():
    """Convert audio to text using Whisper via Ollama.

    Accepts: multipart/form-data with 'audio' file field
             or raw audio bytes in request body.
    Query params:
        language: ISO code (default: de)
    Returns: {"ok": true, "text": "...", "language": "de"}
    """
    import requests as http_requests

    language = request.args.get("language", "de")

    # Get audio data
    audio_data = None
    if "audio" in request.files:
        audio_data = request.files["audio"].read()
    elif request.data:
        audio_data = request.data

    if not audio_data:
        return jsonify({"ok": False, "error": "No audio data provided"}), 400

    # Save to temp file for Whisper
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        # Try Ollama Whisper endpoint
        try:
            with open(tmp_path, "rb") as f:
                resp = http_requests.post(
                    f"{OLLAMA_URL}/api/audio/transcriptions",
                    files={"file": ("audio.wav", f, "audio/wav")},
                    data={"model": STT_MODEL, "language": language},
                    timeout=30,
                )
            if resp.status_code == 200:
                result = resp.json()
                text = result.get("text", "").strip()
                _LOGGER.info("STT transcription: %s (lang=%s)", text[:100], language)
                return jsonify({"ok": True, "text": text, "language": language})
        except Exception as exc:
            _LOGGER.debug("Ollama Whisper not available: %s", exc)

        # Fallback: try OpenAI-compatible whisper endpoint
        cloud_url = os.environ.get("CLOUD_API_URL", "").strip()
        cloud_key = os.environ.get("CLOUD_API_KEY", "").strip()
        if cloud_url and cloud_key:
            base = cloud_url.rstrip("/")
            if base.endswith("/chat/completions"):
                base = base[: -len("/chat/completions")]
            try:
                with open(tmp_path, "rb") as f:
                    resp = http_requests.post(
                        f"{base}/audio/transcriptions",
                        files={"file": ("audio.wav", f, "audio/wav")},
                        data={"model": "whisper-1", "language": language},
                        headers={"Authorization": f"Bearer {cloud_key}"},
                        timeout=30,
                    )
                if resp.status_code == 200:
                    text = resp.json().get("text", "").strip()
                    return jsonify({"ok": True, "text": text, "language": language})
            except Exception as exc:
                _LOGGER.debug("Cloud STT not available: %s", exc)

        return jsonify({"ok": False, "error": "No STT provider available"}), 503

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════
# POST /api/v1/styx/tts — Text-to-Speech
# ═══════════════════════════════════════════════════════════════════════

@styx_voice_bp.route("/tts", methods=["POST"])
def text_to_speech():
    """Convert text to audio using edge-tts or Piper.

    Accepts JSON: {"text": "Hello", "language": "de", "voice": "de-DE-ConradNeural"}
    Returns: audio/mp3 binary stream
    """
    body = request.get_json(silent=True) or {}
    text = str(body.get("text", "")).strip()
    if not text:
        return jsonify({"ok": False, "error": "No text provided"}), 400

    voice = body.get("voice", TTS_VOICE)
    language = body.get("language", "de")

    # Limit text length
    if len(text) > 5000:
        text = text[:5000]

    if TTS_ENGINE == "edge-tts":
        return _tts_edge(text, voice)

    return jsonify({"ok": False, "error": f"Unknown TTS engine: {TTS_ENGINE}"}), 400


def _tts_edge(text: str, voice: str):
    """Generate speech using edge-tts (Microsoft Edge TTS, no API key needed)."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["edge-tts", "--voice", voice, "--text", text, "--write-media", tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            _LOGGER.warning("edge-tts failed: %s", result.stderr[:200])
            # Fallback: try with a different voice
            result = subprocess.run(
                ["edge-tts", "--voice", "de-DE-KatjaNeural", "--text", text, "--write-media", tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            _LOGGER.info("TTS generated: %d chars, voice=%s", len(text), voice)
            return send_file(
                tmp_path,
                mimetype="audio/mpeg",
                as_attachment=False,
                download_name="speech.mp3",
            )

        _LOGGER.error("edge-tts produced no output (rc=%d)", result.returncode)
        return jsonify({"ok": False, "error": "TTS generation failed"}), 503

    except FileNotFoundError:
        _LOGGER.error("edge-tts not installed")
        return jsonify({"ok": False, "error": "edge-tts not installed"}), 503
    except subprocess.TimeoutExpired:
        _LOGGER.error("edge-tts timed out")
        return jsonify({"ok": False, "error": "TTS generation timed out"}), 504
    except Exception as exc:
        _LOGGER.exception("TTS error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════
# GET /api/v1/styx/voice/status — Voice service health
# ═══════════════════════════════════════════════════════════════════════

@styx_voice_bp.route("/voice/status", methods=["GET"])
def voice_status():
    """Return availability of STT and TTS services."""
    import shutil

    stt_available = False
    tts_available = False

    # Check Ollama for STT (whisper)
    try:
        import requests as http_requests
        resp = http_requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            stt_available = any("whisper" in m.lower() for m in models)
    except Exception:
        pass

    # Check edge-tts availability
    tts_available = shutil.which("edge-tts") is not None

    return jsonify({
        "ok": True,
        "stt": {
            "available": stt_available,
            "engine": "whisper" if stt_available else "none",
            "model": STT_MODEL,
        },
        "tts": {
            "available": tts_available,
            "engine": TTS_ENGINE,
            "voice": TTS_VOICE,
        },
    })
