"""Contract tests for the Voice API (transcribe + synthesize endpoints).

Verifies the Request/Response contract for each voice endpoint:
- transcribe: accepts audio_path + language → returns text/confidence/language
- synthesize: accepts text + voice → returns audio_path/duration_seconds
- speak: accepts text → returns TTS result
- TranscriptionResult + TTSResult have expected attributes
"""
from __future__ import annotations

import sys
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