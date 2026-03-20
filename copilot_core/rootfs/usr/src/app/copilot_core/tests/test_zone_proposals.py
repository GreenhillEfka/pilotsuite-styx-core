"""Tests for explainable habitus zone proposals."""
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from copilot_core.habitus_miner.model import MiningConfig, NormEvent
from copilot_core.habitus_miner.service import HabitusMinerService
from copilot_core.habitus_miner.zone_mining import ZoneBasedMiner


class MockTagZoneIntegration:
    """Minimal mock for zone proposal tests."""

    def __init__(self, zones: dict[str, list[str]]):
        self._zones = zones

    def get_all_zones(self) -> list[str]:
        return list(self._zones.keys())

    def get_entities_for_zone(self, zone_id: str) -> list[str]:
        return self._zones.get(zone_id, [])


def create_event(entity_id: str, state: str, ts_ms: int, *, hour: str = "20") -> NormEvent:
    return NormEvent(
        ts=ts_ms,
        key=f"{entity_id}:{state}",
        entity_id=entity_id,
        domain=entity_id.split(".", 1)[0],
        transition=state,
        context={"hour": hour, "weekday": "2", "time_of_day": "evening"},
    )


class TestSensorNormalization:
    def test_buckets_numeric_sensor_states(self, tmp_path):
        service = HabitusMinerService(storage_dir=tmp_path)
        event = service.normalize_ha_event({
            "time_fired": "2026-03-18T19:30:00Z",
            "event_type": "state_changed",
            "data": {
                "entity_id": "sensor.living_room_illuminance",
                "old_state": {"state": "220"},
                "new_state": {"state": "18"},
            },
            "context": {"source": "ha"},
        })

        assert event is not None
        assert event.transition == "dark"
        assert event.key == "sensor.living_room_illuminance:dark"

    def test_ignores_sensor_changes_inside_same_bucket(self, tmp_path):
        service = HabitusMinerService(storage_dir=tmp_path)
        event = service.normalize_ha_event({
            "time_fired": "2026-03-18T19:31:00Z",
            "event_type": "state_changed",
            "data": {
                "entity_id": "sensor.living_room_illuminance",
                "old_state": {"state": "20"},
                "new_state": {"state": "35"},
            },
            "context": {"source": "ha"},
        })

        assert event is None


class TestZoneProposalLayer:
    @pytest.fixture
    def miner(self):
        zones = {
            "zone:wohnzimmer": [
                "binary_sensor.wohnzimmer_presence",
                "sensor.wohnzimmer_illuminance",
                "media_player.wohnzimmer_tv",
                "light.wohnzimmer_main",
                "cover.wohnzimmer_blinds",
            ]
        }
        config = MiningConfig(
            windows=[10, 30],
            min_support_A=5,
            min_support_B=5,
            min_hits=5,
            min_confidence=0.6,
            min_confidence_lb=0.3,
            min_lift=1.1,
            min_leverage=0.0,
            min_stability_days=1,
        )
        return ZoneBasedMiner(MockTagZoneIntegration(zones), config)

    @pytest.fixture
    def events(self):
        base_ts = int(datetime(2026, 3, 10, 19, 0).timestamp() * 1000)
        events = []

        for i in range(12):
            offset = i * 60000
            # Presence -> lights on
            events.append(create_event("binary_sensor.wohnzimmer_presence", "on", base_ts + offset))
            events.append(create_event("light.wohnzimmer_main", "on", base_ts + offset + 3000))
            # Media -> blinds close for ambience
            events.append(create_event("media_player.wohnzimmer_tv", "playing", base_ts + offset + 15000))
            events.append(create_event("cover.wohnzimmer_blinds", "closed", base_ts + offset + 20000))
            # Darkness -> lights on
            events.append(create_event("sensor.wohnzimmer_illuminance", "dark", base_ts + offset + 30000))
            events.append(create_event("light.wohnzimmer_main", "on", base_ts + offset + 32000))
            # Absence -> media idle / lights off
            events.append(create_event("binary_sensor.wohnzimmer_presence", "off", base_ts + offset + 45000))
            events.append(create_event("media_player.wohnzimmer_tv", "idle", base_ts + offset + 50000))
            events.append(create_event("light.wohnzimmer_main", "off", base_ts + offset + 52000))

        return events

    def test_builds_explainable_zone_proposals(self, miner, events):
        results = miner.mine_all_zones(events)
        proposals = miner.build_zone_proposals(results, limit=10, min_confidence=0.55)

        assert proposals
        proposal_types = {proposal["type"] for proposal in proposals}
        assert "presence_lights_on" in proposal_types
        assert "media_sets_ambience" in proposal_types
        assert "sensor_driven_adjustment" in proposal_types
        assert "absence_turns_devices_off" in proposal_types or "absence_quiets_media" in proposal_types

        for proposal in proposals:
            assert 0.55 <= proposal["confidence"] <= 1.0
            assert proposal["confidence_breakdown"]["stable_confidence"] >= 0.0
            assert proposal["confidence_breakdown"]["support_score"] > 0.0
            assert "automation_preview" in proposal
            assert "evidence" in proposal
            assert "module_id" in proposal
            assert proposal["action"]["module_id"] == proposal["module_id"]
            assert proposal["explanation"]
            assert proposal["title"]

    def test_export_results_includes_proposals_summary(self, miner, events):
        results = miner.mine_all_zones(events)
        exported = miner.export_results(results, proposal_limit=5, proposal_min_confidence=0.55)

        assert "proposals" in exported
        assert exported["summary"]["total_proposals"] == len(exported["proposals"])
        assert exported["summary"]["total_zones"] == 1
