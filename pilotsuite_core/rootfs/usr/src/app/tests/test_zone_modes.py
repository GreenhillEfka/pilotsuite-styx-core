"""Tests for Zone Modes engine (v6.6.0)."""

import pytest
from datetime import datetime, timedelta, timezone
from copilot_core.hub.zone_modes import (
    ZoneModeEngine,
    ModeDefinition,
    ActiveMode,
    ModeEvent,
    ZoneModeStatus,
    ModeOverview,
)


@pytest.fixture
def engine():
    return ZoneModeEngine()


# ── Built-in modes ─────────────────────────────────────────────────────────


class TestBuiltinModes:
    def test_builtin_modes_count(self, engine):
        modes = engine.get_available_modes()
        assert len(modes) == 8

    def test_builtin_mode_ids(self, engine):
        modes = engine.get_available_modes()
        ids = {m["mode_id"] for m in modes}
        assert ids == {"party", "kids_sleep", "movie", "guest", "focus", "away", "night", "romantic"}

    def test_party_mode_definition(self, engine):
        modes = engine.get_available_modes()
        party = next(m for m in modes if m["mode_id"] == "party")
        assert party["name_de"] == "Partymodus"
        assert party["name_en"] == "Party Mode"
        assert party["icon"] == "mdi:party-popper"
        assert party["default_duration_min"] == 180
        assert party["suppresses"]["automations"] is True
        assert party["suppresses"]["notifications"] is True
        assert party["suppresses"]["lights"] is False

    def test_kids_sleep_mode_restrictions(self, engine):
        modes = engine.get_available_modes()
        ks = next(m for m in modes if m["mode_id"] == "kids_sleep")
        assert ks["suppresses"]["automations"] is True
        assert ks["suppresses"]["lights"] is True
        assert ks["suppresses"]["media"] is True
        assert ks["suppresses"]["notifications"] is True


# ── Mode activation ────────────────────────────────────────────────────────


class TestModeActivation:
    def test_activate_mode(self, engine):
        result = engine.activate_mode("wohnzimmer", "party")
        assert result is True

    def test_activate_invalid_mode(self, engine):
        result = engine.activate_mode("wohnzimmer", "nonexistent")
        assert result is False

    def test_activated_mode_visible_in_status(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        status = engine.get_zone_status("wohnzimmer")
        assert status.active_mode == "party"
        assert status.mode_name_de == "Partymodus"
        assert status.icon == "mdi:party-popper"

    def test_activate_with_default_duration(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        status = engine.get_zone_status("wohnzimmer")
        assert status.expires_at is not None
        assert status.remaining_min is not None
        assert status.remaining_min > 0

    def test_activate_with_custom_duration(self, engine):
        engine.activate_mode("wohnzimmer", "party", duration_min=60)
        status = engine.get_zone_status("wohnzimmer")
        assert status.remaining_min is not None
        assert status.remaining_min <= 60

    def test_activate_indefinite_mode(self, engine):
        engine.activate_mode("wohnzimmer", "night")
        status = engine.get_zone_status("wohnzimmer")
        assert status.expires_at is None
        assert status.remaining_min is None

    def test_activate_overrides_previous(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        engine.activate_mode("wohnzimmer", "movie")
        status = engine.get_zone_status("wohnzimmer")
        assert status.active_mode == "movie"

    def test_activate_multiple_zones(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        engine.activate_mode("schlafzimmer", "kids_sleep")
        s1 = engine.get_zone_status("wohnzimmer")
        s2 = engine.get_zone_status("schlafzimmer")
        assert s1.active_mode == "party"
        assert s2.active_mode == "kids_sleep"

    def test_activated_by_field(self, engine):
        engine.activate_mode("wohnzimmer", "party", activated_by="automation")
        overview = engine.get_overview()
        active = next(m for m in overview.active_modes if m["zone_id"] == "wohnzimmer")
        assert active["activated_by"] == "automation"


# ── Mode deactivation ──────────────────────────────────────────────────────


class TestModeDeactivation:
    def test_deactivate_mode(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        result = engine.deactivate_mode("wohnzimmer")
        assert result is True

    def test_deactivate_clears_status(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        engine.deactivate_mode("wohnzimmer")
        status = engine.get_zone_status("wohnzimmer")
        assert status.active_mode is None

    def test_deactivate_nonexistent(self, engine):
        result = engine.deactivate_mode("nonexistent")
        assert result is False


# ── Expiration ─────────────────────────────────────────────────────────────


class TestExpiration:
    def test_check_expirations_no_expired(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        expired = engine.check_expirations()
        assert expired == []

    def test_check_expirations_with_expired(self, engine):
        engine.activate_mode("wohnzimmer", "party", duration_min=1)
        # Manually set expiry to past
        active = engine._active["wohnzimmer"]
        active.expires_at = datetime.now(tz=timezone.utc) - timedelta(minutes=1)
        expired = engine.check_expirations()
        assert "wohnzimmer" in expired

    def test_expired_mode_cleared(self, engine):
        engine.activate_mode("wohnzimmer", "party", duration_min=1)
        active = engine._active["wohnzimmer"]
        active.expires_at = datetime.now(tz=timezone.utc) - timedelta(minutes=1)
        engine.check_expirations()
        status = engine.get_zone_status("wohnzimmer")
        assert status.active_mode is None

    def test_indefinite_mode_does_not_expire(self, engine):
        engine.activate_mode("wohnzimmer", "night")
        expired = engine.check_expirations()
        assert expired == []
        status = engine.get_zone_status("wohnzimmer")
        assert status.active_mode == "night"


# ── Suppression checks ────────────────────────────────────────────────────


class TestSuppression:
    def test_no_suppression_without_mode(self, engine):
        assert engine.is_suppressed("wohnzimmer", "automations") is False

    def test_party_suppresses_automations(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        assert engine.is_suppressed("wohnzimmer", "automations") is True

    def test_party_does_not_suppress_lights(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        assert engine.is_suppressed("wohnzimmer", "lights") is False

    def test_kids_sleep_suppresses_all(self, engine):
        engine.activate_mode("kinderzimmer", "kids_sleep")
        assert engine.is_suppressed("kinderzimmer", "automations") is True
        assert engine.is_suppressed("kinderzimmer", "lights") is True
        assert engine.is_suppressed("kinderzimmer", "media") is True
        assert engine.is_suppressed("kinderzimmer", "notifications") is True

    def test_guest_suppresses_nothing(self, engine):
        engine.activate_mode("gästezimmer", "guest")
        assert engine.is_suppressed("gästezimmer", "automations") is False
        assert engine.is_suppressed("gästezimmer", "lights") is False
        assert engine.is_suppressed("gästezimmer", "media") is False
        assert engine.is_suppressed("gästezimmer", "notifications") is False


# ── Restrictions ───────────────────────────────────────────────────────────


class TestRestrictions:
    def test_no_restriction_without_mode(self, engine):
        assert engine.get_restriction("wohnzimmer", "max_volume_pct") is None

    def test_kids_sleep_volume_restriction(self, engine):
        engine.activate_mode("kinderzimmer", "kids_sleep")
        assert engine.get_restriction("kinderzimmer", "max_volume_pct") == 20

    def test_kids_sleep_brightness_restriction(self, engine):
        engine.activate_mode("kinderzimmer", "kids_sleep")
        assert engine.get_restriction("kinderzimmer", "max_brightness_pct") == 10

    def test_focus_brightness_min(self, engine):
        engine.activate_mode("büro", "focus")
        assert engine.get_restriction("büro", "min_brightness_pct") == 70

    def test_romantic_color_temp(self, engine):
        engine.activate_mode("wohnzimmer", "romantic")
        assert engine.get_restriction("wohnzimmer", "color_temp_k") == 2200

    def test_zone_status_restrictions(self, engine):
        engine.activate_mode("kinderzimmer", "kids_sleep")
        status = engine.get_zone_status("kinderzimmer")
        assert "max_volume_pct" in status.restrictions
        assert "max_brightness_pct" in status.restrictions
        assert "color_temp_k" in status.restrictions

    def test_zone_status_suppression(self, engine):
        engine.activate_mode("kinderzimmer", "kids_sleep")
        status = engine.get_zone_status("kinderzimmer")
        assert status.suppressed["automations"] is True
        assert status.suppressed["lights"] is True


# ── History ────────────────────────────────────────────────────────────────


class TestHistory:
    def test_activation_recorded(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        overview = engine.get_overview()
        assert len(overview.recent_events) >= 1
        event = overview.recent_events[0]
        assert event["mode_id"] == "party"
        assert event["action"] == "activated"

    def test_deactivation_recorded(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        engine.deactivate_mode("wohnzimmer")
        overview = engine.get_overview()
        events = [e for e in overview.recent_events if e["action"] == "deactivated"]
        assert len(events) == 1

    def test_override_recorded(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        engine.activate_mode("wohnzimmer", "movie")
        overview = engine.get_overview()
        events = [e for e in overview.recent_events if e["action"] == "overridden"]
        assert len(events) == 1

    def test_expiry_recorded(self, engine):
        engine.activate_mode("wohnzimmer", "party", duration_min=1)
        engine._active["wohnzimmer"].expires_at = datetime.now(tz=timezone.utc) - timedelta(minutes=1)
        engine.check_expirations()
        overview = engine.get_overview()
        events = [e for e in overview.recent_events if e["action"] == "expired"]
        assert len(events) == 1


# ── Overview ───────────────────────────────────────────────────────────────


class TestOverview:
    def test_empty_overview(self, engine):
        overview = engine.get_overview()
        assert overview.total_zones_with_modes == 0
        assert len(overview.active_modes) == 0
        assert len(overview.available_modes) == 8

    def test_overview_with_active_modes(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        engine.activate_mode("schlafzimmer", "night")
        overview = engine.get_overview()
        assert overview.total_zones_with_modes == 2
        assert len(overview.active_modes) == 2

    def test_overview_active_mode_details(self, engine):
        engine.activate_mode("wohnzimmer", "party")
        overview = engine.get_overview()
        active = overview.active_modes[0]
        assert active["zone_id"] == "wohnzimmer"
        assert active["mode_id"] == "party"
        assert active["mode_name_de"] == "Partymodus"
        assert active["icon"] == "mdi:party-popper"


# ── Custom modes ───────────────────────────────────────────────────────────


class TestCustomModes:
    def test_register_custom_mode(self, engine):
        result = engine.register_custom_mode(
            "gaming", "Gaming-Modus", "Gaming Mode",
            icon="mdi:controller",
            suppress_notifications=True,
            max_brightness_pct=40,
            default_duration_min=240,
        )
        assert result is True

    def test_custom_mode_available(self, engine):
        engine.register_custom_mode("gaming", "Gaming-Modus")
        modes = engine.get_available_modes()
        assert len(modes) == 9
        gaming = next(m for m in modes if m["mode_id"] == "gaming")
        assert gaming["name_de"] == "Gaming-Modus"

    def test_custom_mode_activatable(self, engine):
        engine.register_custom_mode("gaming", "Gaming-Modus")
        result = engine.activate_mode("wohnzimmer", "gaming")
        assert result is True
        status = engine.get_zone_status("wohnzimmer")
        assert status.active_mode == "gaming"

    def test_duplicate_custom_mode_rejected(self, engine):
        engine.register_custom_mode("gaming", "Gaming-Modus")
        result = engine.register_custom_mode("gaming", "Gaming-Modus 2")
        assert result is False

    def test_builtin_mode_id_rejected(self, engine):
        result = engine.register_custom_mode("party", "My Party")
        assert result is False
