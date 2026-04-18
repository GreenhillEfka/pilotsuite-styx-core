"""Contract tests for the shipped add-on voice compatibility surface."""
from __future__ import annotations

from pathlib import Path


def test_voice_whisper_module_is_importable():
    from copilot_core.voice.stt_whisper import WhisperSTT

    stt = WhisperSTT()
    result = stt.transcribe("dummy.wav")

    assert result is not None
    assert result.text
    assert result.language


def test_voice_piper_module_is_importable(tmp_path):
    from copilot_core.voice.tts_piper import PiperTTS, TTSConfig

    tts = PiperTTS(TTSConfig(output_dir=str(tmp_path)))
    result = tts.synthesize("Hallo Welt")

    assert result is not None
    assert Path(result.audio_path).exists()
    assert result.voice


def test_voice_nlu_extract_intent_reports_light_domain():
    from copilot_core.voice.nlu_engine import NLUEngine

    intent = NLUEngine().extract_intent("Turn on the living room lights")

    assert intent["intent"] == "turn_on"
    assert "light" in intent["domain"].lower()
