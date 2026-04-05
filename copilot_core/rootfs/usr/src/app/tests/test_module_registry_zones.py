"""Tests for ModuleRegistry per-zone state management (v14.2.0)."""

import os
import tempfile

import pytest

from copilot_core.module_registry import ModuleRegistry


@pytest.fixture
def registry(tmp_path):
    """Create a fresh ModuleRegistry with temp DB."""
    db_path = str(tmp_path / "test_modules.db")
    ModuleRegistry._reset_instance()
    reg = ModuleRegistry(db_path=db_path)
    yield reg
    ModuleRegistry._reset_instance()


class TestZoneModuleStates:
    """Per-zone module state CRUD."""

    def test_get_zone_state_falls_back_to_global(self, registry):
        """Zone state should fall back to global when no override."""
        registry.set_state("licht", "learning")
        assert registry.get_zone_state("wohnbereich", "licht") == "learning"

    def test_get_zone_state_default(self, registry):
        """Default state is 'active' when nothing configured."""
        assert registry.get_zone_state("wohnbereich", "licht") == "active"

    def test_set_zone_state(self, registry):
        """Setting zone state should persist and override global."""
        registry.set_state("licht", "active")
        registry.set_zone_state("wohnbereich", "licht", "off")
        assert registry.get_zone_state("wohnbereich", "licht") == "off"
        # Global state unchanged
        assert registry.get_state("licht") == "active"

    def test_set_zone_state_invalid(self, registry):
        """Invalid state should be rejected."""
        assert registry.set_zone_state("wohnbereich", "licht", "invalid") is False

    def test_set_zone_state_valid_states(self, registry):
        """All valid states should be accepted."""
        for state in ("active", "learning", "off"):
            assert registry.set_zone_state("wohnbereich", "licht", state) is True
            assert registry.get_zone_state("wohnbereich", "licht") == state

    def test_zone_state_independent_per_zone(self, registry):
        """Different zones can have different states for same module."""
        registry.set_zone_state("wohnbereich", "licht", "active")
        registry.set_zone_state("schlafzimmer", "licht", "off")
        assert registry.get_zone_state("wohnbereich", "licht") == "active"
        assert registry.get_zone_state("schlafzimmer", "licht") == "off"

    def test_get_zone_states(self, registry):
        """get_zone_states returns all per-zone overrides."""
        registry.set_zone_state("wohnbereich", "licht", "active")
        registry.set_zone_state("wohnbereich", "musik", "learning")
        registry.set_zone_state("wohnbereich", "bewegung", "off")

        states = registry.get_zone_states("wohnbereich")
        assert states == {
            "bewegung": "off",
            "licht": "active",
            "musik": "learning",
        }

    def test_get_zone_states_empty(self, registry):
        """Empty result when no overrides for zone."""
        assert registry.get_zone_states("nonexistent") == {}

    def test_get_all_zone_states(self, registry):
        """get_all_zone_states groups by zone."""
        registry.set_zone_state("wohnbereich", "licht", "active")
        registry.set_zone_state("schlafzimmer", "musik", "off")

        all_states = registry.get_all_zone_states()
        assert "wohnbereich" in all_states
        assert "schlafzimmer" in all_states
        assert all_states["wohnbereich"]["licht"] == "active"
        assert all_states["schlafzimmer"]["musik"] == "off"

    def test_zone_state_update(self, registry):
        """Updating zone state should overwrite."""
        registry.set_zone_state("wohnbereich", "licht", "active")
        registry.set_zone_state("wohnbereich", "licht", "off")
        assert registry.get_zone_state("wohnbereich", "licht") == "off"

    def test_delete_zone_state_restores_global_fallback(self, registry):
        """Deleting a zone override should restore the global state."""
        registry.set_state("licht", "learning")
        registry.set_zone_state("wohnbereich", "licht", "off")

        assert registry.delete_zone_state("wohnbereich", "licht") is True
        assert registry.get_zone_state("wohnbereich", "licht") == "learning"
        assert registry.get_zone_states("wohnbereich") == {}

    def test_delete_zone_state_missing(self, registry):
        """Deleting a missing zone override should be a no-op."""
        assert registry.delete_zone_state("wohnbereich", "licht") is False


class TestShouldAutoApplyZone:
    """Double-safety at zone level."""

    def test_both_active(self, registry):
        """Auto-apply when both source and target active in zone."""
        registry.set_zone_state("wohnbereich", "mood", "active")
        registry.set_zone_state("wohnbereich", "licht", "active")
        assert registry.should_auto_apply_zone("wohnbereich", "mood", "licht") is True

    def test_target_learning(self, registry):
        """No auto-apply when target is learning."""
        registry.set_zone_state("wohnbereich", "mood", "active")
        registry.set_zone_state("wohnbereich", "licht", "learning")
        assert registry.should_auto_apply_zone("wohnbereich", "mood", "licht") is False

    def test_source_off(self, registry):
        """No auto-apply when source is off."""
        registry.set_zone_state("wohnbereich", "mood", "off")
        registry.set_zone_state("wohnbereich", "licht", "active")
        assert registry.should_auto_apply_zone("wohnbereich", "mood", "licht") is False

    def test_falls_back_to_global(self, registry):
        """Uses global state when no zone override."""
        # Global defaults are 'active', so should auto-apply
        assert registry.should_auto_apply_zone("wohnbereich", "mood", "licht") is True

    def test_mixed_zone_and_global(self, registry):
        """Zone override + global default mixed."""
        registry.set_zone_state("wohnbereich", "mood", "off")
        # licht has no zone override, global default is "active"
        assert registry.should_auto_apply_zone("wohnbereich", "mood", "licht") is False


class TestBusIntegration:
    """Bus event publishing on zone state changes."""

    def test_publishes_zone_state_changed(self, registry):
        """Should publish module.zone_state_changed on zone state change."""
        events = []

        class FakeBus:
            def publish(self, event_type, data, source=""):
                events.append({"type": event_type, "data": data})

        registry.set_bus(FakeBus())
        registry.set_zone_state("wohnbereich", "licht", "off")

        assert len(events) == 1
        assert events[0]["type"] == "module.zone_state_changed"
        assert events[0]["data"]["zone_id"] == "wohnbereich"
        assert events[0]["data"]["module_id"] == "licht"
        assert events[0]["data"]["new_state"] == "off"
