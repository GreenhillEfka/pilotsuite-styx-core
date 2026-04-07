"""Tests for Scene Intelligence + PilotSuite Cloud (v7.0.0)."""

import pytest
from copilot_core.hub.scene_intelligence import (
    SceneIntelligenceEngine,
    SceneContext,
    ScenePreset,
    SceneSuggestion,
    LearnedPattern,
    CloudStatus,
    SceneIntelligenceDashboard,
)


@pytest.fixture
def engine():
    return SceneIntelligenceEngine()


# ── Built-in scenes ──────────────────────────────────────────────────────────


class TestBuiltinScenes:
    def test_has_10_builtin_scenes(self, engine):
        scenes = engine.get_scenes()
        assert len(scenes) == 10

    def test_scene_ids(self, engine):
        ids = {s["scene_id"] for s in engine.get_scenes()}
        expected = {
            "morning_routine", "work_focus", "lunch_break", "afternoon_relax",
            "dinner_time", "movie_night", "romantic_evening", "bedtime",
            "party", "away",
        }
        assert ids == expected

    def test_scenes_have_german_names(self, engine):
        for s in engine.get_scenes():
            assert s["name_de"], f"Scene {s['scene_id']} has no name_de"

    def test_filter_by_category(self, engine):
        evening = engine.get_scenes(category="evening")
        assert len(evening) == 3
        assert all(s["category"] == "evening" for s in evening)

    def test_filter_by_nonexistent_category(self, engine):
        result = engine.get_scenes(category="nonexistent")
        assert result == []


# ── Activation / Deactivation ───────────────────────────────────────────────


class TestActivation:
    def test_activate_scene(self, engine):
        assert engine.activate_scene("morning_routine") is True

    def test_activate_with_zone(self, engine):
        assert engine.activate_scene("party", zone_id="wohnzimmer") is True
        active = engine.get_active_scene()
        assert active["zone_id"] == "wohnzimmer"

    def test_activate_unknown_scene(self, engine):
        assert engine.activate_scene("nonexistent") is False

    def test_get_active_scene(self, engine):
        engine.activate_scene("movie_night")
        active = engine.get_active_scene()
        assert active is not None
        assert active["scene_id"] == "movie_night"
        assert active["name_de"] == "Filmabend"
        assert active["light_brightness_pct"] == 10

    def test_no_active_scene(self, engine):
        assert engine.get_active_scene() is None

    def test_deactivate_scene(self, engine):
        engine.activate_scene("bedtime")
        assert engine.deactivate_scene() is True
        assert engine.get_active_scene() is None

    def test_deactivate_when_none_active(self, engine):
        assert engine.deactivate_scene() is False

    def test_usage_count_increments(self, engine):
        engine.activate_scene("party")
        engine.activate_scene("party")
        engine.activate_scene("party")
        scenes = engine.get_scenes()
        party = next(s for s in scenes if s["scene_id"] == "party")
        assert party["usage_count"] == 3

    def test_activation_log_capped(self, engine):
        for _ in range(120):
            engine.activate_scene("morning_routine")
        assert len(engine._activation_log) == 100


# ── Suggestions ─────────────────────────────────────────────────────────────


class TestSuggestions:
    def test_morning_suggestion(self, engine):
        ctx = SceneContext(hour=7, is_home=True)
        suggestions = engine.suggest_scenes(ctx, limit=5)
        assert len(suggestions) > 0
        ids = [s.scene_id for s in suggestions]
        assert "morning_routine" in ids

    def test_evening_suggestions(self, engine):
        ctx = SceneContext(hour=20, is_home=True, occupancy_count=2)
        suggestions = engine.suggest_scenes(ctx, limit=10)
        ids = [s.scene_id for s in suggestions]
        assert any(sid in ids for sid in ["dinner_time", "movie_night", "romantic_evening"])

    def test_night_suggestion(self, engine):
        ctx = SceneContext(hour=23, is_home=True)
        suggestions = engine.suggest_scenes(ctx, limit=5)
        ids = [s.scene_id for s in suggestions]
        assert "bedtime" in ids

    def test_away_suggestion(self, engine):
        ctx = SceneContext(hour=12, is_home=False)
        suggestions = engine.suggest_scenes(ctx, limit=5)
        ids = [s.scene_id for s in suggestions]
        assert "away" in ids

    def test_party_suggestion_high_occupancy(self, engine):
        ctx = SceneContext(hour=20, is_home=True, occupancy_count=5)
        suggestions = engine.suggest_scenes(ctx, limit=10)
        ids = [s.scene_id for s in suggestions]
        assert "party" in ids

    def test_work_focus_weekday(self, engine):
        ctx = SceneContext(hour=10, is_home=True, is_weekend=False)
        suggestions = engine.suggest_scenes(ctx, limit=10)
        ids = [s.scene_id for s in suggestions]
        assert "work_focus" in ids

    def test_suggestions_have_confidence(self, engine):
        ctx = SceneContext(hour=7)
        suggestions = engine.suggest_scenes(ctx, limit=3)
        for s in suggestions:
            assert isinstance(s.confidence, float)
            assert s.confidence > 0

    def test_suggestions_have_reason(self, engine):
        ctx = SceneContext(hour=7)
        suggestions = engine.suggest_scenes(ctx, limit=3)
        morning = next((s for s in suggestions if s.scene_id == "morning_routine"), None)
        assert morning is not None
        assert morning.reason_de != ""

    def test_suggestions_default_context(self, engine):
        suggestions = engine.suggest_scenes(limit=5)
        assert isinstance(suggestions, list)

    def test_suggestion_limit(self, engine):
        ctx = SceneContext(hour=20)
        suggestions = engine.suggest_scenes(ctx, limit=2)
        assert len(suggestions) <= 2


# ── Pattern Learning ────────────────────────────────────────────────────────


class TestPatternLearning:
    def test_learn_no_patterns_without_data(self, engine):
        count = engine.learn_patterns()
        assert count == 0

    def test_learn_patterns_from_activations(self, engine):
        # Activate same scene 5 times at same hour to build a pattern
        from datetime import datetime, timezone
        for _ in range(5):
            ctx = SceneContext(hour=8)
            engine._activation_log.append(
                (datetime.now(tz=timezone.utc), "morning_routine", ctx)
            )
        count = engine.learn_patterns()
        assert count == 1
        assert len(engine._patterns) == 1
        assert engine._patterns[0].scene_id == "morning_routine"

    def test_learn_patterns_minimum_threshold(self, engine):
        from datetime import datetime, timezone
        for _ in range(2):  # only 2, below threshold of 3
            ctx = SceneContext(hour=8)
            engine._activation_log.append(
                (datetime.now(tz=timezone.utc), "morning_routine", ctx)
            )
        count = engine.learn_patterns()
        assert count == 0

    def test_patterns_boost_suggestions(self, engine):
        engine._patterns.append(LearnedPattern(
            pattern_id="test_pattern",
            scene_id="movie_night",
            hour_range=(19, 22),
            activation_count=10,
        ))
        ctx = SceneContext(hour=20, is_home=True)
        suggestions = engine.suggest_scenes(ctx, limit=10)
        movie = next((s for s in suggestions if s.scene_id == "movie_night"), None)
        assert movie is not None
        assert movie.confidence > 0.4


# ── Cloud ───────────────────────────────────────────────────────────────────


class TestCloud:
    def test_initial_cloud_disconnected(self, engine):
        status = engine.get_cloud_status()
        assert status["connected"] is False
        assert status["cloud_url"] == ""

    def test_configure_cloud(self, engine):
        result = engine.configure_cloud("https://cloud.pilotsuite.de", 30)
        assert result.connected is True
        assert result.sync_interval_min == 30

    def test_configure_cloud_empty_url_disconnects(self, engine):
        engine.configure_cloud("https://cloud.pilotsuite.de")
        result = engine.configure_cloud("")
        assert result.connected is False

    def test_share_scene_requires_connection(self, engine):
        assert engine.share_scene("morning_routine") is False

    def test_share_scene_connected(self, engine):
        engine.configure_cloud("https://cloud.pilotsuite.de")
        assert engine.share_scene("morning_routine") is True
        status = engine.get_cloud_status()
        assert status["shared_scenes"] == 1

    def test_share_unknown_scene(self, engine):
        engine.configure_cloud("https://cloud.pilotsuite.de")
        assert engine.share_scene("nonexistent") is False

    def test_cloud_status_dict(self, engine):
        engine.configure_cloud("https://cloud.pilotsuite.de")
        status = engine.get_cloud_status()
        assert "connected" in status
        assert "last_sync" in status
        assert "sync_interval_min" in status
        assert "local_fallback" in status


# ── Custom Scenes ───────────────────────────────────────────────────────────


class TestCustomScenes:
    def test_register_custom_scene(self, engine):
        result = engine.register_scene("reading", "Lesezeit", "Reading Time")
        assert result is True
        assert len(engine.get_scenes()) == 11

    def test_register_duplicate_fails(self, engine):
        assert engine.register_scene("morning_routine", "Duplicate") is False

    def test_custom_scene_with_kwargs(self, engine):
        engine.register_scene(
            "yoga", "Yoga", "Yoga",
            light_brightness_pct=50,
            climate_temp_c=22.0,
            category="activity",
        )
        scenes = engine.get_scenes(category="activity")
        ids = [s["scene_id"] for s in scenes]
        assert "yoga" in ids


# ── Rating ──────────────────────────────────────────────────────────────────


class TestRating:
    def test_rate_scene(self, engine):
        assert engine.rate_scene("morning_routine", 4.0) is True

    def test_rate_scene_average(self, engine):
        engine.rate_scene("morning_routine", 4.0)
        engine.rate_scene("morning_routine", 2.0)
        scenes = engine.get_scenes()
        mr = next(s for s in scenes if s["scene_id"] == "morning_routine")
        assert mr["rating"] == 3.0

    def test_rate_invalid_score(self, engine):
        assert engine.rate_scene("morning_routine", 0) is False
        assert engine.rate_scene("morning_routine", 6) is False

    def test_rate_unknown_scene(self, engine):
        assert engine.rate_scene("nonexistent", 3.0) is False


# ── Dashboard ───────────────────────────────────────────────────────────────


class TestDashboard:
    def test_dashboard_structure(self, engine):
        db = engine.get_dashboard()
        assert isinstance(db, SceneIntelligenceDashboard)
        assert db.total_scenes == 10
        assert db.active_scene is None
        assert isinstance(db.suggestions, list)
        assert isinstance(db.cloud_status, dict)
        assert isinstance(db.categories, dict)
        assert isinstance(db.popular_scenes, list)

    def test_dashboard_with_active_scene(self, engine):
        engine.activate_scene("party")
        db = engine.get_dashboard()
        assert db.active_scene is not None
        assert db.active_scene["scene_id"] == "party"

    def test_dashboard_categories(self, engine):
        db = engine.get_dashboard()
        assert "morning" in db.categories
        assert "evening" in db.categories
        assert "night" in db.categories

    def test_dashboard_popular_scenes(self, engine):
        engine.activate_scene("party")
        engine.activate_scene("party")
        engine.activate_scene("bedtime")
        db = engine.get_dashboard()
        assert len(db.popular_scenes) > 0
        assert db.popular_scenes[0]["scene_id"] == "party"
