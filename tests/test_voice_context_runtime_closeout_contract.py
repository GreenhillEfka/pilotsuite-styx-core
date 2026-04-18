"""Tests for residual context-runtime closeout on internal voice callers (P3-011-K)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.voice.context_builder import (  # noqa: E402
    TimeContext,
    VoiceContext,
    VoiceContextRuntime,
)
from copilot_core.voice.proactive import ProactiveVoiceHints  # noqa: E402
from copilot_core.voice.voice_handler import (  # noqa: E402
    IntentType,
    VoiceIntent,
    VoiceIntentHandler,
)


class _RecordingBuilder:
    def __init__(self, context: VoiceContext):
        self.context = context
        self.calls: list[dict] = []

    def build_context(self, **kwargs):
        self.calls.append(kwargs)
        return self.context


def test_voice_intent_handler_self_builds_context_through_context_runtime():
    mood_engine = object()
    habitus_service = object()
    context = VoiceContext(
        zone_name="wohnzimmer",
        time_context=TimeContext(),
    )
    builder = _RecordingBuilder(context)
    handler = VoiceIntentHandler(
        mood_engine=mood_engine,
        habitus_service=habitus_service,
        default_language="de",
    )
    handler._context_builder = builder

    response = handler.handle_intent(
        VoiceIntent(intent_type=IntentType.STATUS_QUERY, confidence=0.91, raw_text="Status"),
        context=None,
    )

    assert response.tts_text
    assert len(builder.calls) == 1
    kwargs = builder.calls[0]
    assert "mood_engine" not in kwargs
    assert "habitus_service" not in kwargs
    assert isinstance(kwargs["context_runtime"], VoiceContextRuntime)
    assert kwargs["context_runtime"].mood_engine is mood_engine
    assert kwargs["context_runtime"].habitus_service is habitus_service


def test_proactive_hints_self_builds_context_through_context_runtime(monkeypatch):
    mood_engine = object()
    habitus_service = object()
    context = VoiceContext(
        zone_name="wohnzimmer",
        time_context=TimeContext(),
    )
    builder = _RecordingBuilder(context)
    hints = ProactiveVoiceHints(
        mood_engine=mood_engine,
        habitus_service=habitus_service,
    )
    hints.context_builder = builder
    monkeypatch.setattr(hints, "_check_mood_changes", lambda context: [])
    monkeypatch.setattr(hints, "_check_time_routines", lambda context: [])
    monkeypatch.setattr(hints, "_check_habitus_patterns", lambda context: [])
    monkeypatch.setattr(hints, "_check_environment_hints", lambda context: [])

    assert hints.generate_hints(context=None, force=True) == []
    assert len(builder.calls) == 1
    kwargs = builder.calls[0]
    assert "mood_engine" not in kwargs
    assert "habitus_service" not in kwargs
    assert isinstance(kwargs["context_runtime"], VoiceContextRuntime)
    assert kwargs["context_runtime"].mood_engine is mood_engine
    assert kwargs["context_runtime"].habitus_service is habitus_service
