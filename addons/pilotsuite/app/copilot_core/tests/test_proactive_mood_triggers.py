"""Tests for Proactive Mood Triggers — ProactiveContextEngine.evaluate_mood_trigger().

Covers:
- Mood transition suggestions (comfort recovery, bedtime, focus)
- Delta threshold filtering (small changes suppressed)
- Quiet hours suppression
- NeuronManager._evaluate_proactive_suggestions() integration
- Suggestion callback forwarding
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from copilot_core.proactive_engine import ProactiveContextEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _offset_for_local_hour(target_hour: int) -> str:
    """Compute TZ_OFFSET so that current UTC maps to *target_hour* locally."""
    utc_hour = datetime.now(timezone.utc).hour
    return str((target_hour - utc_hour) % 24)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _daytime(monkeypatch):
    """Force local hour to 14:00 so quiet-hours (23-7) never interfere."""
    monkeypatch.setenv("TZ_OFFSET", _offset_for_local_hour(14))


@pytest.fixture
def engine():
    """Create a bare ProactiveContextEngine."""
    return ProactiveContextEngine()


# ---------------------------------------------------------------------------
# evaluate_mood_trigger — basic transitions
# ---------------------------------------------------------------------------

class TestMoodTriggerBasic:
    def test_comfort_recovery_on_alert_transition(self, engine):
        suggestions = engine.evaluate_mood_trigger(
            new_mood="alert", confidence=0.8,
            previous_mood="relax", previous_confidence=0.5,
        )
        assert len(suggestions) >= 1
        assert suggestions[0]["type"] == "proactive_mood"
        assert suggestions[0]["subtype"] == "comfort_recovery"

    def test_bedtime_transition(self, engine):
        suggestions = engine.evaluate_mood_trigger(
            new_mood="sleep", confidence=0.7,
            previous_mood="relax", previous_confidence=0.6,
        )
        subtypes = [s["subtype"] for s in suggestions]
        assert "bedtime_transition" in subtypes

    def test_focus_mode_transition(self, engine):
        suggestions = engine.evaluate_mood_trigger(
            new_mood="focus", confidence=0.75,
            previous_mood="social", previous_confidence=0.5,
        )
        subtypes = [s["subtype"] for s in suggestions]
        assert "focus_mode" in subtypes

    def test_no_suggestion_for_same_mood(self, engine):
        """No suggestions when mood stays the same with small delta."""
        suggestions = engine.evaluate_mood_trigger(
            new_mood="relax", confidence=0.6,
            previous_mood="relax", previous_confidence=0.55,
        )
        assert len(suggestions) == 0

    def test_suggestion_contains_mood_from_to(self, engine):
        suggestions = engine.evaluate_mood_trigger(
            new_mood="sleep", confidence=0.8,
            previous_mood="relax", previous_confidence=0.5,
        )
        assert len(suggestions) >= 1
        assert suggestions[0]["mood_from"] == "relax"
        assert suggestions[0]["mood_to"] == "sleep"


# ---------------------------------------------------------------------------
# Delta threshold
# ---------------------------------------------------------------------------

class TestDeltaThreshold:
    def test_below_threshold_suppressed(self, engine):
        """Delta < 0.15 with same mood → no suggestions."""
        suggestions = engine.evaluate_mood_trigger(
            new_mood="relax", confidence=0.60,
            previous_mood="relax", previous_confidence=0.50,
        )
        assert len(suggestions) == 0

    def test_above_threshold_triggers(self, engine):
        """Delta >= 0.15 with different mood → suggestions generated."""
        suggestions = engine.evaluate_mood_trigger(
            new_mood="alert", confidence=0.8,
            previous_mood="relax", previous_confidence=0.5,
        )
        assert len(suggestions) >= 1

    def test_mood_change_even_with_small_delta(self, engine):
        """Different mood triggers even if delta is small, if mood actually changed."""
        suggestions = engine.evaluate_mood_trigger(
            new_mood="sleep", confidence=0.55,
            previous_mood="active", previous_confidence=0.50,
        )
        # sleep != active → at least bedtime suggestion
        assert len(suggestions) >= 1


# ---------------------------------------------------------------------------
# Quiet hours
# ---------------------------------------------------------------------------

class TestQuietHours:
    @staticmethod
    def _offset_for_local_hour(target_hour: int) -> str:
        """Compute TZ_OFFSET so that current UTC maps to target local hour."""
        utc_hour = datetime.now(timezone.utc).hour
        return str((target_hour - utc_hour) % 24)

    def test_quiet_hours_suppression(self, engine):
        """During quiet hours (23-7), no suggestions."""
        offset = self._offset_for_local_hour(3)  # local hour 3 → inside quiet
        with patch.dict(os.environ, {"TZ_OFFSET": offset,
                                     "QUIET_HOUR_START": "23",
                                     "QUIET_HOUR_END": "7"}):
            suggestions = engine.evaluate_mood_trigger(
                new_mood="alert", confidence=0.9,
                previous_mood="relax", previous_confidence=0.5,
            )
            assert len(suggestions) == 0

    def test_outside_quiet_hours_allowed(self, engine):
        """During daytime (14:00), suggestions are generated."""
        offset = self._offset_for_local_hour(14)  # local hour 14 → outside quiet
        with patch.dict(os.environ, {"TZ_OFFSET": offset,
                                     "QUIET_HOUR_START": "23",
                                     "QUIET_HOUR_END": "7"}):
            suggestions = engine.evaluate_mood_trigger(
                new_mood="alert", confidence=0.9,
                previous_mood="relax", previous_confidence=0.5,
            )
            assert len(suggestions) >= 1


# ---------------------------------------------------------------------------
# Suggestion fields
# ---------------------------------------------------------------------------

class TestSuggestionFields:
    def test_suggestion_has_required_fields(self, engine):
        suggestions = engine.evaluate_mood_trigger(
            new_mood="sleep", confidence=0.8,
            previous_mood="active", previous_confidence=0.5,
        )
        assert len(suggestions) >= 1
        s = suggestions[0]
        assert "type" in s
        assert "subtype" in s
        assert "priority" in s
        assert "message" in s
        assert "confidence" in s
        assert "dismissible" in s

    def test_suggestion_is_dismissible(self, engine):
        suggestions = engine.evaluate_mood_trigger(
            new_mood="focus", confidence=0.8,
            previous_mood="social", previous_confidence=0.5,
        )
        for s in suggestions:
            assert s["dismissible"] is True

    def test_zone_id_passed_through(self, engine):
        suggestions = engine.evaluate_mood_trigger(
            new_mood="sleep", confidence=0.8,
            previous_mood="relax", previous_confidence=0.5,
            zone_id="schlafzimmer",
        )
        assert len(suggestions) >= 1
        assert suggestions[0]["zone_id"] == "schlafzimmer"


# ---------------------------------------------------------------------------
# NeuronManager integration
# ---------------------------------------------------------------------------

class TestNeuronManagerIntegration:
    def test_set_proactive_engine(self):
        from copilot_core.neurons.manager import NeuronManager
        manager = NeuronManager()
        engine = ProactiveContextEngine()
        manager.set_proactive_engine(engine)
        assert manager._proactive_engine is engine

    def test_evaluate_proactive_suggestions_calls_engine(self):
        from copilot_core.neurons.manager import NeuronManager
        manager = NeuronManager()
        engine = MagicMock()
        engine.evaluate_mood_trigger.return_value = [
            {"type": "proactive_mood", "subtype": "test"}
        ]
        manager.set_proactive_engine(engine)

        callback = MagicMock()
        manager.on_suggestion(callback)

        manager._evaluate_proactive_suggestions("alert", 0.8)
        engine.evaluate_mood_trigger.assert_called_once()
        callback.assert_called_once()

    def test_no_engine_no_crash(self):
        from copilot_core.neurons.manager import NeuronManager
        manager = NeuronManager()
        # Should not raise
        manager._evaluate_proactive_suggestions("alert", 0.8)

    def test_engine_error_handled(self):
        from copilot_core.neurons.manager import NeuronManager
        manager = NeuronManager()
        engine = MagicMock()
        engine.evaluate_mood_trigger.side_effect = RuntimeError("boom")
        manager.set_proactive_engine(engine)
        # Should not raise
        manager._evaluate_proactive_suggestions("alert", 0.8)

    def test_mood_changed_triggers_proactive(self):
        from copilot_core.neurons.manager import NeuronManager, NeuralPipelineResult
        manager = NeuronManager()
        engine = MagicMock()
        engine.evaluate_mood_trigger.return_value = []
        manager.set_proactive_engine(engine)

        # Simulate a previous result
        manager._last_result = NeuralPipelineResult(
            timestamp="2025-01-01T00:00:00",
            context_values={}, state_values={}, mood_values={},
            dominant_mood="relax", mood_confidence=0.6,
            suggestions=[], neuron_states={},
        )

        manager._on_mood_changed("alert", 0.8)
        engine.evaluate_mood_trigger.assert_called_once_with(
            new_mood="alert", confidence=0.8,
            previous_mood="relax", previous_confidence=0.6,
        )
