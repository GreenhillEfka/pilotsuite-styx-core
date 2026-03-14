"""Tests for AutonomyExecutor — Governance checks and execution logic."""

import time
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from copilot_core.autonomy.executor import AutonomyExecutor, ExecutionResult, _RATE_LIMIT_SECONDS
from copilot_core.autonomy.ha_bridge import ServiceCallResult


# ── Fixtures ────────────────────────────────────────────────────────────

class FakeZoneAutomation:
    """Minimal ZoneAutomationController stub."""

    def __init__(self, mode="autonomy"):
        self._mode = mode
        self._entities = {}

    def get_automation_mode(self, zone_id):
        return self._mode

    def get_all_states(self):
        return [{"zone_id": "wohnbereich", "automation_mode": self._mode, "occupied": True}]

    def get_zone_entities_by_role(self, zone_id):
        return self._entities.get(zone_id, {})


class FakeModuleRegistry:
    """Minimal ModuleRegistry stub."""

    def __init__(self, zone_states=None):
        self._zone_states = zone_states or {}

    def get_zone_state(self, zone_id, module_id):
        return self._zone_states.get(f"{zone_id}:{module_id}", "active")

    def should_auto_apply_zone(self, zone_id, source, target):
        src = self.get_zone_state(zone_id, source)
        tgt = self.get_zone_state(zone_id, target)
        return src == "active" and tgt == "active"

    def get_zone_states(self, zone_id):
        result = {}
        for key, val in self._zone_states.items():
            if key.startswith(f"{zone_id}:"):
                mod = key.split(":")[1]
                result[mod] = val
        return result


class FakeHABridge:
    """Minimal HABridge stub."""

    def __init__(self):
        self.calls = []

    def turn_on_light(self, entity_id, brightness_pct=100, color_temp_k=None):
        self.calls.append(("turn_on", entity_id, brightness_pct, color_temp_k))
        return ServiceCallResult(ok=True, domain="light", service="turn_on")

    def turn_off_light(self, entity_id):
        self.calls.append(("turn_off", entity_id))
        return ServiceCallResult(ok=True, domain="light", service="turn_off")


class FakeBus:
    def __init__(self):
        self.events = []

    def publish(self, event_type, data, source=""):
        self.events.append({"type": event_type, "data": data})


@pytest.fixture
def executor():
    """Executor with all dependencies stubbed."""
    return AutonomyExecutor(
        zone_automation=FakeZoneAutomation(mode="autonomy"),
        module_registry=FakeModuleRegistry(),
        ha_bridge=FakeHABridge(),
        behavioral_log=MagicMock(),
        bus=FakeBus(),
    )


# ── Governance Tests ────────────────────────────────────────────────────

class TestGovernanceChecks:
    def test_zone_off_skips(self):
        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="off"),
            module_registry=FakeModuleRegistry(),
        )
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test", "brightness_pct": 50}],
            "test",
        )
        assert result.decision == "skipped"
        assert "off" in result.reason

    def test_zone_learning_suggests(self):
        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="learning"),
            module_registry=FakeModuleRegistry(),
            behavioral_log=MagicMock(),
        )
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test"}],
            "test",
        )
        assert result.decision == "suggested"

    def test_module_off_skips(self):
        registry = FakeModuleRegistry(zone_states={"wohnbereich:licht": "off"})
        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=registry,
        )
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test"}],
            "test",
        )
        assert result.decision == "skipped"

    def test_module_learning_suggests(self):
        registry = FakeModuleRegistry(zone_states={"wohnbereich:licht": "learning"})
        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=registry,
            behavioral_log=MagicMock(),
        )
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test"}],
            "test",
        )
        assert result.decision == "suggested"

    def test_double_safety_blocks(self):
        registry = FakeModuleRegistry(zone_states={
            "wohnbereich:mood": "active",
            "wohnbereich:licht": "learning",
        })
        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=registry,
            behavioral_log=MagicMock(),
        )
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test"}],
            "test", source_module="mood",
        )
        assert result.decision == "suggested"

    def test_all_active_executes(self, executor):
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test", "brightness_pct": 50}],
            "test mood",
        )
        assert result.decision == "executed"
        assert len(executor._ha_bridge.calls) == 1

    def test_no_zone_automation_defaults_off(self):
        executor = AutonomyExecutor()
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test"}],
            "test",
        )
        assert result.decision == "skipped"


# ── Execution Tests ─────────────────────────────────────────────────────

class TestExecution:
    def test_light_turn_on(self, executor):
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.decke", "brightness_pct": 50, "color_temp_k": 2700}],
            "test",
        )
        assert result.decision == "executed"
        call = executor._ha_bridge.calls[0]
        assert call[0] == "turn_on"
        assert call[1] == "light.decke"
        assert call[2] == 50
        assert call[3] == 2700

    def test_light_turn_off(self, executor):
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_off", "entity_id": "light.decke"}],
            "test",
        )
        assert result.decision == "executed"
        assert executor._ha_bridge.calls[0][0] == "turn_off"

    def test_multiple_actions(self, executor):
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [
                {"type": "light.turn_on", "entity_id": "light.a", "brightness_pct": 50},
                {"type": "light.turn_on", "entity_id": "light.b", "brightness_pct": 50},
            ],
            "test",
        )
        assert result.decision == "executed"
        assert len(executor._ha_bridge.calls) == 2

    def test_publishes_bus_event(self, executor):
        executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test", "brightness_pct": 50}],
            "test",
        )
        assert len(executor._bus.events) == 1
        assert executor._bus.events[0]["type"] == "autonomy.executed"


# ── Rate Limiting ───────────────────────────────────────────────────────

class TestRateLimiting:
    def test_rate_limit_blocks_second_call(self, executor):
        executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test", "brightness_pct": 50}],
            "first",
        )
        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test", "brightness_pct": 80}],
            "second",
        )
        assert result.decision == "skipped"
        assert "Rate limited" in result.reason

    def test_rate_limit_different_module(self, executor):
        executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.test", "brightness_pct": 50}],
            "light",
        )
        # Different module should not be rate limited
        executor._musikwolke_bridge = MagicMock()
        executor._musikwolke_bridge.play_in_zone.return_value = True
        result = executor.execute_if_allowed(
            "wohnbereich", "musik",
            [{"type": "music.play", "volume_pct": 30}],
            "music",
        )
        assert result.decision == "executed"


# ── Event Handler Tests ─────────────────────────────────────────────────

class TestOnMoodChanged:
    def test_mood_event_triggers_actions(self):
        zone_auto = FakeZoneAutomation(mode="autonomy")
        zone_auto._entities = {
            "wohnbereich": {
                "lights": [{"entity_id": "light.wohnzimmer_decke"}],
            },
        }
        ha_bridge = FakeHABridge()
        executor = AutonomyExecutor(
            zone_automation=zone_auto,
            module_registry=FakeModuleRegistry(),
            ha_bridge=ha_bridge,
            behavioral_log=MagicMock(),
            bus=FakeBus(),
        )

        @dataclass
        class FakeEvent:
            data: dict

        executor.on_mood_changed(FakeEvent(data={
            "mood": "relax",
            "confidence": 0.85,
        }))

        assert len(ha_bridge.calls) >= 1

    def test_empty_mood_ignored(self):
        executor = AutonomyExecutor()

        @dataclass
        class FakeEvent:
            data: dict

        # Should not raise
        executor.on_mood_changed(FakeEvent(data={}))


class TestOnPresenceChanged:
    def test_presence_detected_triggers_light(self):
        zone_auto = FakeZoneAutomation(mode="autonomy")
        zone_auto._entities = {
            "wohnbereich": {
                "lights": [{"entity_id": "light.decke"}],
            },
        }
        ha_bridge = FakeHABridge()
        neuron_mgr = MagicMock()

        @dataclass
        class FakeResult:
            dominant_mood: str = "relax"
            mood_confidence: float = 0.8
            context_values: dict = None

            def __post_init__(self):
                if self.context_values is None:
                    self.context_values = {}

        neuron_mgr.get_last_result.return_value = FakeResult()

        executor = AutonomyExecutor(
            zone_automation=zone_auto,
            module_registry=FakeModuleRegistry(),
            ha_bridge=ha_bridge,
            behavioral_log=MagicMock(),
            neuron_manager=neuron_mgr,
            bus=FakeBus(),
        )

        @dataclass
        class FakeEvent:
            data: dict

        executor.on_presence_changed(FakeEvent(data={
            "zone_id": "wohnbereich",
            "detected": True,
        }))

        assert len(ha_bridge.calls) >= 1

    def test_presence_cleared_turns_off(self):
        zone_auto = FakeZoneAutomation(mode="autonomy")
        zone_auto._entities = {
            "wohnbereich": {
                "lights": [{"entity_id": "light.decke"}],
            },
        }
        ha_bridge = FakeHABridge()

        executor = AutonomyExecutor(
            zone_automation=zone_auto,
            module_registry=FakeModuleRegistry(),
            ha_bridge=ha_bridge,
            behavioral_log=MagicMock(),
            bus=FakeBus(),
        )

        @dataclass
        class FakeEvent:
            data: dict

        executor.on_presence_changed(FakeEvent(data={
            "zone_id": "wohnbereich",
            "detected": False,
        }))

        assert any(c[0] == "turn_off" for c in ha_bridge.calls)


# ── Dashboard ───────────────────────────────────────────────────────────

class TestDashboard:
    def test_dashboard_structure(self, executor):
        dashboard = executor.get_dashboard()
        assert "zones" in dashboard
        assert "stats" in dashboard
        assert "log" in dashboard
        assert "rate_limit_seconds" in dashboard
        assert dashboard["rate_limit_seconds"] == _RATE_LIMIT_SECONDS

    def test_dashboard_without_deps(self):
        executor = AutonomyExecutor()
        dashboard = executor.get_dashboard()
        assert dashboard["zones"] == {}


# ── Action Execution Tests ─────────────────────────────────────────────

class TestExecuteActions:
    """Tests for specific action execution paths (music, light errors)."""

    def test_music_play_favorite_success(self):
        """music.play_favorite with working musikwolke_bridge + sonos."""
        mock_sonos = MagicMock()
        mock_sonos.play_favorite = MagicMock()

        mock_mw = MagicMock()
        mock_mw._sonos = mock_sonos

        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=FakeModuleRegistry(),
            ha_bridge=FakeHABridge(),
            behavioral_log=MagicMock(),
            musikwolke_bridge=mock_mw,
            bus=FakeBus(),
        )

        result = executor.execute_if_allowed(
            "wohnbereich", "musik",
            [{"type": "music.play_favorite", "room": "Wohnzimmer", "favorite": "Chill Mix", "volume_pct": 30}],
            "test mood",
        )
        assert result.decision == "executed"
        mock_sonos.play_favorite.assert_called_once_with("Wohnzimmer", "Chill Mix")
        mock_mw.set_zone_volume.assert_called_once_with("wohnbereich", 30)

    def test_music_play_favorite_no_sonos(self):
        """music.play_favorite when _sonos is None records error."""
        mock_mw = MagicMock()
        mock_mw._sonos = None

        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=FakeModuleRegistry(),
            ha_bridge=FakeHABridge(),
            behavioral_log=MagicMock(),
            musikwolke_bridge=mock_mw,
            bus=FakeBus(),
        )

        result = executor.execute_if_allowed(
            "wohnbereich", "musik",
            [{"type": "music.play_favorite", "room": "Wohnzimmer", "favorite": "Chill Mix"}],
            "test",
        )
        # No executed actions because sonos is None
        assert result.decision == "skipped"
        assert "sonos client unavailable" in result.error

    def test_music_play(self):
        """music.play action calls play_in_zone."""
        mock_mw = MagicMock()
        mock_mw.play_in_zone.return_value = True

        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=FakeModuleRegistry(),
            behavioral_log=MagicMock(),
            musikwolke_bridge=mock_mw,
            bus=FakeBus(),
        )

        result = executor.execute_if_allowed(
            "wohnbereich", "musik",
            [{"type": "music.play", "volume_pct": 40}],
            "test",
        )
        assert result.decision == "executed"
        mock_mw.play_in_zone.assert_called_once_with("wohnbereich", volume_pct=40)

    def test_music_pause(self):
        """music.pause action calls pause_in_zone."""
        mock_mw = MagicMock()

        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=FakeModuleRegistry(),
            behavioral_log=MagicMock(),
            musikwolke_bridge=mock_mw,
            bus=FakeBus(),
        )

        result = executor.execute_if_allowed(
            "wohnbereich", "musik",
            [{"type": "music.pause"}],
            "test",
        )
        assert result.decision == "executed"
        mock_mw.pause_in_zone.assert_called_once_with("wohnbereich")

    def test_light_turn_on_ha_error(self):
        """light.turn_on when ha_bridge returns ok=False records error."""
        ha_bridge = MagicMock()
        ha_bridge.turn_on_light.return_value = ServiceCallResult(
            ok=False, domain="light", service="turn_on", error="entity not found",
        )

        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=FakeModuleRegistry(),
            ha_bridge=ha_bridge,
            behavioral_log=MagicMock(),
            bus=FakeBus(),
        )

        result = executor.execute_if_allowed(
            "wohnbereich", "licht",
            [{"type": "light.turn_on", "entity_id": "light.nope", "brightness_pct": 50}],
            "test",
        )
        assert result.decision == "skipped"
        assert "light error" in result.error


# ── Music Error Handling ───────────────────────────────────────────────

class TestMusicErrorHandling:
    """Verify music actions record errors when bridge is unavailable."""

    def test_play_favorite_no_bridge(self):
        """music.play_favorite without musikwolke_bridge records error."""
        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=FakeModuleRegistry(),
            ha_bridge=FakeHABridge(),
            behavioral_log=MagicMock(),
            musikwolke_bridge=None,
            bus=FakeBus(),
        )

        result = executor.execute_if_allowed(
            "wohnbereich", "musik",
            [{"type": "music.play_favorite", "room": "Wohnzimmer", "favorite": "Mix"}],
            "test",
        )
        assert result.decision == "skipped"
        assert "musikwolke_bridge unavailable" in result.error

    def test_play_no_bridge(self):
        """music.play without musikwolke_bridge records error."""
        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=FakeModuleRegistry(),
            behavioral_log=MagicMock(),
            musikwolke_bridge=None,
            bus=FakeBus(),
        )

        result = executor.execute_if_allowed(
            "wohnbereich", "musik",
            [{"type": "music.play", "volume_pct": 30}],
            "test",
        )
        assert result.decision == "skipped"
        assert "musikwolke_bridge unavailable" in result.error

    def test_pause_no_bridge(self):
        """music.pause without musikwolke_bridge records error."""
        executor = AutonomyExecutor(
            zone_automation=FakeZoneAutomation(mode="autonomy"),
            module_registry=FakeModuleRegistry(),
            behavioral_log=MagicMock(),
            musikwolke_bridge=None,
            bus=FakeBus(),
        )

        result = executor.execute_if_allowed(
            "wohnbereich", "musik",
            [{"type": "music.pause"}],
            "test",
        )
        assert result.decision == "skipped"
        assert "musikwolke_bridge unavailable" in result.error
