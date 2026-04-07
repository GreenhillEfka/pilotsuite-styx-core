"""Tests for MoodActionMapper and mood-action tables."""

import json
import os

import pytest

from copilot_core.autonomy.mood_actions import (
    MoodActionMapper,
    MoodActionSet,
    _DEFAULT_ACTIONS,
)


@pytest.fixture
def mapper(tmp_path):
    """Mapper with temp overrides file."""
    path = str(tmp_path / "mood_actions.json")
    return MoodActionMapper(overrides_path=path)


class TestMoodActionSet:
    """MoodActionSet dataclass."""

    def test_defaults(self):
        action = MoodActionSet(mood="test")
        assert action.brightness_pct == 0
        assert action.music_action == "none"

    def test_to_dict_roundtrip(self):
        original = MoodActionSet(
            mood="relax", brightness_pct=50, color_temp_k=2700,
        )
        d = original.to_dict()
        restored = MoodActionSet.from_dict(d)
        assert restored.mood == "relax"
        assert restored.brightness_pct == 50
        assert restored.color_temp_k == 2700

    def test_from_dict_ignores_unknown(self):
        d = {"mood": "test", "unknown_field": 42, "brightness_pct": 80}
        action = MoodActionSet.from_dict(d)
        assert action.mood == "test"
        assert action.brightness_pct == 80


class TestDefaultActions:
    """Default mood-action table."""

    def test_all_moods_covered(self):
        expected = {"relax", "focus", "sleep", "active", "social", "away", "alert", "recovery"}
        assert set(_DEFAULT_ACTIONS.keys()) == expected

    def test_relax_values(self):
        r = _DEFAULT_ACTIONS["relax"]
        assert r.brightness_pct == 50
        assert r.color_temp_k == 2700
        assert r.music_favorite == "Chill Lounge"
        assert r.music_action == "play"

    def test_focus_pauses_music(self):
        f = _DEFAULT_ACTIONS["focus"]
        assert f.music_action == "pause"

    def test_away_turns_off(self):
        a = _DEFAULT_ACTIONS["away"]
        assert a.brightness_pct == 0
        assert a.music_action == "pause"


class TestMoodActionMapper:
    """Mapper lookup, overrides, weather overlay."""

    def test_basic_lookup(self, mapper):
        result = mapper.get_mood_actions("relax")
        assert result.mood == "relax"
        assert result.brightness_pct == 50

    def test_unknown_mood_returns_neutral(self, mapper):
        result = mapper.get_mood_actions("unknown_mood")
        assert result.mood == "unknown_mood"
        assert result.brightness_pct == 0

    def test_does_not_mutate_default(self, mapper):
        # Get twice — second call should still return defaults
        r1 = mapper.get_mood_actions("relax", weather_score=0.1)
        r2 = mapper.get_mood_actions("relax")
        assert r2.music_favorite == "Chill Lounge"  # Not modified

    def test_get_all_actions(self, mapper):
        all_actions = mapper.get_all_actions()
        assert "relax" in all_actions
        assert "focus" in all_actions
        assert all_actions["relax"]["overridden"] is False


class TestWeatherOverlay:
    """Weather-based music adjustments."""

    def test_cloudy_triggers_uplift(self, mapper):
        result = mapper.get_mood_actions("relax", weather_score=0.2)
        assert result.music_favorite == "Sunny Feel-Good"

    def test_sunny_no_uplift(self, mapper):
        result = mapper.get_mood_actions("relax", weather_score=0.8)
        assert result.music_favorite == "Chill Lounge"

    def test_no_uplift_for_active(self, mapper):
        result = mapper.get_mood_actions("active", weather_score=0.1)
        assert result.music_favorite == "Feel Good Hits"

    def test_no_uplift_for_focus(self, mapper):
        result = mapper.get_mood_actions("focus", weather_score=0.1)
        assert result.music_action == "pause"

    def test_no_uplift_for_away(self, mapper):
        result = mapper.get_mood_actions("away", weather_score=0.1)
        assert result.music_action == "pause"

    def test_none_weather_no_uplift(self, mapper):
        result = mapper.get_mood_actions("relax", weather_score=None)
        assert result.music_favorite == "Chill Lounge"


class TestOverrides:
    """User override persistence."""

    def test_set_override(self, mapper):
        result = mapper.set_override("relax", {"brightness_pct": 70})
        assert result.brightness_pct == 70
        assert result.mood == "relax"
        # Original fields preserved
        assert result.color_temp_k == 2700

    def test_override_persists(self, tmp_path):
        path = str(tmp_path / "mood_actions.json")
        m1 = MoodActionMapper(overrides_path=path)
        m1.set_override("relax", {"brightness_pct": 80})

        # New mapper loads from file
        m2 = MoodActionMapper(overrides_path=path)
        result = m2.get_mood_actions("relax")
        assert result.brightness_pct == 80

    def test_override_shows_in_all_actions(self, mapper):
        mapper.set_override("relax", {"brightness_pct": 99})
        all_actions = mapper.get_all_actions()
        assert all_actions["relax"]["overridden"] is True
        assert all_actions["relax"]["brightness_pct"] == 99

    def test_remove_override(self, mapper):
        mapper.set_override("relax", {"brightness_pct": 99})
        assert mapper.remove_override("relax") is True
        result = mapper.get_mood_actions("relax")
        assert result.brightness_pct == 50  # Back to default

    def test_remove_nonexistent_override(self, mapper):
        assert mapper.remove_override("nonexistent") is False
