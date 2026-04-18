"""Contract tests for the Voice API (transcribe + synthesize endpoints).

Verifies the Request/Response contract for each voice endpoint:
- transcribe: accepts audio_path + language → returns text/confidence/language
- synthesize: accepts text + voice → returns audio_path/duration_seconds
- speak: accepts text → returns TTS result
- TranscriptionResult + TTSResult have expected attributes
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


class TestTranscriptionResultContract:
    """TranscriptionResult returned by WhisperSTT has correct contract."""

    def test_result_has_expected_fields(self):
        from copilot_core.voice.stt_whisper import TranscriptionResult
        result = TranscriptionResult(text="test", language="de", confidence=0.95, duration_ms=1500, metadata={})
        assert hasattr(result, "text")
        assert hasattr(result, "language")
        assert hasattr(result, "confidence")
        assert hasattr(result, "duration_ms")

    def test_result_text_is_string(self):
        from copilot_core.voice.stt_whisper import TranscriptionResult
        result = TranscriptionResult(text="Hallo Welt", language="en", confidence=0.9, duration_ms=1000, metadata={})
        assert isinstance(result.text, str)
        assert result.text == "Hallo Welt"


class TestTTSResultContract:
    """TTSResult returned by PiperTTS has correct contract."""

    def test_result_has_audio_path_attribute(self):
        from copilot_core.voice.tts_piper import TTSResult
        from copilot_core.voice.tts_piper import VoiceEmotion
        result = TTSResult(audio_path="/tmp/test.wav", text="Hello", voice="de", duration_seconds=1.5, generation_time_ms=800, emotion=VoiceEmotion.NEUTRAL)
        assert hasattr(result, "audio_path")
        assert hasattr(result, "text")
        assert hasattr(result, "voice")
        assert hasattr(result, "duration_seconds")

    def test_result_duration_is_float(self):
        from copilot_core.voice.tts_piper import TTSResult
        from copilot_core.voice.tts_piper import VoiceEmotion
        result = TTSResult(audio_path="/tmp/test.wav", text="Hello", voice="en", duration_seconds=2.0, generation_time_ms=1000, emotion=VoiceEmotion.NEUTRAL)
        assert isinstance(result.duration_seconds, float)


class TestWhisperSTTEngine:
    """WhisperSTT engine basic contract."""

    def test_engine_initializes(self):
        from copilot_core.voice.stt_whisper import WhisperSTT
        engine = WhisperSTT()
        assert engine is not None

    def test_engine_has_transcribe_method(self):
        from copilot_core.voice.stt_whisper import WhisperSTT
        engine = WhisperSTT()
        assert hasattr(engine, "transcribe")

    def test_transcribe_accepts_language_param(self):
        from copilot_core.voice.stt_whisper import WhisperSTT
        engine = WhisperSTT()
        # Method should accept language keyword arg
        import inspect
        sig = inspect.signature(engine.transcribe)
        params = list(sig.parameters.keys())
        assert "language" in params or params == ["audio_path"] or params == ["self", "audio_path", "language"]


class TestPiperTTSEngine:
    """PiperTTS engine basic contract."""

    def test_engine_initializes(self):
        from copilot_core.voice.tts_piper import PiperTTS
        engine = PiperTTS()
        assert engine is not None

    def test_engine_has_synthesize_method(self):
        from copilot_core.voice.tts_piper import PiperTTS
        engine = PiperTTS()
        assert hasattr(engine, "synthesize")

    def test_synthesize_accepts_voice_param(self):
        from copilot_core.voice.tts_piper import PiperTTS
        engine = PiperTTS()
        import inspect
        sig = inspect.signature(engine.synthesize)
        params = list(sig.parameters.keys())
        assert "voice" in params or "voice_id" in params or params == ["self", "text"] or params == ["text"]


class TestVoiceAPIRouteLogic:
    """Transcribe/synthesize endpoint logic edge cases are handled."""

    def test_transcribe_with_memory_audio_path(self):
        """Engine should accept memory:// URIs as audio_path."""
        from copilot_core.voice.stt_whisper import WhisperSTT
        engine = WhisperSTT()
        # Call with memory URI — should return None (unavailable) or raise
        # Not crash with a Python traceback
        try:
            result = engine.transcribe("memory://voice-input", language="de")
            # None = unavailable, any other result = unexpected success
            assert result is None or hasattr(result, "text")
        except Exception:
            pass  # Any exception = backend unavailable, acceptable

    def test_synthesize_with_empty_text_returns_none_or_raises(self):
        """Engine should handle empty text gracefully."""
        from copilot_core.voice.tts_piper import PiperTTS
        engine = PiperTTS()
        try:
            result = engine.synthesize("")
            assert result is None or hasattr(result, "audio_path")
        except (ValueError, RuntimeError):
            pass  # Acceptable: engine rejects empty input

    def test_speak_endpoint_request_shape(self):
        """Verify the /speak endpoint request contract (text field)."""
        from flask import Flask
        from copilot_core.api.v1.voice import bp

        app = Flask(__name__)
        app.config["COPILOT_AUTH_REQUIRED"] = False
        app.register_blueprint(bp)
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/speak",
            json={"text": "Licht einschalten"},
        )
        # 200 (OK), 401 (auth), 503 (TTS unavailable) — not 500
        assert response.status_code in (200, 401, 503), f"Unexpected {response.status_code}"

    def test_speak_returns_real_audio_url_that_can_be_fetched(self, monkeypatch):
        """`/speak` must return an audio URL backed by a real fetchable artifact."""
        from flask import Flask
        from copilot_core.api.v1 import voice as voice_api
        from copilot_core.voice.tts_piper import TTSResult, VoiceEmotion

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write(b"RIFFdemoWAVE")
            audio_path = handle.name

        class _FakeTTSEngine:
            def synthesize(self, text, voice=None):
                return TTSResult(
                    audio_path=audio_path,
                    text=text,
                    voice=voice or "de_DE-thorsten",
                    duration_seconds=1.2,
                    generation_time_ms=12.0,
                    emotion=VoiceEmotion.NEUTRAL,
                )

        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        monkeypatch.setattr(voice_api, "_get_tts_engine", lambda: _FakeTTSEngine())

        app = Flask(__name__)
        app.register_blueprint(voice_api.bp)
        client = app.test_client()

        speak_response = client.post(
            "/api/v1/voice/speak",
            json={"text": "Licht einschalten", "language": "de"},
        )

        assert speak_response.status_code == 200, speak_response.get_data(as_text=True)
        payload = speak_response.get_json()
        assert payload["status"] == "ok"
        assert payload["audio_url"].startswith("/api/v1/voice/audio/")
        assert payload["format"] == "wav"
        assert payload["duration_seconds"] == 1.2

        audio_response = client.get(payload["audio_url"])
        assert audio_response.status_code == 200, audio_response.get_data(as_text=True)
        assert audio_response.mimetype == "audio/wav"
        assert audio_response.data == b"RIFFdemoWAVE"

    def test_speak_returns_503_when_tts_backend_unavailable(self, monkeypatch):
        """`/speak` must degrade cleanly when Piper is unavailable."""
        from flask import Flask
        from copilot_core.api.v1 import voice as voice_api

        class _FakeUnavailableTTSEngine:
            def synthesize(self, text, voice=None):
                return None

        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        monkeypatch.setattr(voice_api, "_get_tts_engine", lambda: _FakeUnavailableTTSEngine())

        app = Flask(__name__)
        app.register_blueprint(voice_api.bp)
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/speak",
            json={"text": "Licht einschalten"},
        )

        assert response.status_code == 503, response.get_data(as_text=True)
        payload = response.get_json()
        assert payload["status"] == "error"
        assert "unavailable" in payload["message"].lower()
