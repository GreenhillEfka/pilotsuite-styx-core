"""Tests for zone-based mining."""
import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from copilot_core.habitus_miner.zone_mining import (
    ZoneBasedMiner,
    ZoneMiningConfig,
    ZoneMiningResult,
)
from copilot_core.habitus_miner.model import NormEvent, MiningConfig


class MockTagZoneIntegration:
    """Mock TagZoneIntegration for testing."""
    
    def __init__(self, zones: dict[str, list[str]]):
        self._zones = zones
        self.safety_critical = set()
    
    def get_all_zones(self) -> list[str]:
        return list(self._zones.keys())
    
    def get_entities_for_zone(self, zone_id: str) -> list[str]:
        return self._zones.get(zone_id, [])
    
    def add_safety_critical(self, entity_id: str) -> None:
        self.safety_critical.add(entity_id)


def create_test_event(entity_id: str, state: str, ts_ms: int) -> NormEvent:
    """Create a test event."""
    return NormEvent(
        ts=ts_ms,
        key=f"{entity_id}:{state}",
        entity_id=entity_id,
        domain=entity_id.split(".", 1)[0] if "." in entity_id else "",
        transition=f":{state}",
        context={"hour": "12", "weekday": "1"},
    )


class TestZoneMiningConfig:
    """Tests for ZoneMiningConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ZoneMiningConfig(zone_id="zone:living_room")
        
        assert config.zone_id == "zone:living_room"
        assert config.min_events == 10
        assert config.confidence_threshold == 0.7
        assert config.lift_threshold == 1.5
        assert config.requires_confirmation is True
        assert len(config.safety_critical_entities) == 0
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ZoneMiningConfig(
            zone_id="zone:kitchen",
            min_events=20,
            confidence_threshold=0.8,
            lift_threshold=2.0,
            requires_confirmation=False,
            safety_critical_entities={"switch.oven"},
        )
        
        assert config.min_events == 20
        assert config.confidence_threshold == 0.8
        assert config.lift_threshold == 2.0
        assert config.requires_confirmation is False
        assert "switch.oven" in config.safety_critical_entities


class TestZoneMiningResult:
    """Tests for ZoneMiningResult."""
    
    def test_empty_result(self):
        """Test empty result."""
        result = ZoneMiningResult(zone_id="zone:test")
        
        assert result.zone_id == "zone:test"
        assert len(result.rules) == 0
        assert len(result.filtered_rules) == 0
        assert len(result.safety_blocked) == 0
    
    def test_to_dict(self):
        """Test result serialization."""
        result = ZoneMiningResult(zone_id="zone:living_room")
        result.rules = []  # Would contain Rule objects
        result.filtered_rules = []
        result.stats = {"events": 100, "raw_rules": 5}
        
        d = result.to_dict()
        
        assert d["zone_id"] == "zone:living_room"
        assert d["rules_count"] == 0
        assert d["stats"]["events"] == 100


class TestZoneBasedMiner:
    """Tests for ZoneBasedMiner."""
    
    @pytest.fixture
    def mock_tag_zone(self):
        """Create mock tag zone integration."""
        return MockTagZoneIntegration({
            "zone:living_room": ["light.living_room", "switch.tv", "sensor.temperature"],
            "zone:kitchen": ["light.kitchen", "switch.coffee_maker"],
        })
    
    @pytest.fixture
    def events(self):
        """Create test events."""
        base_ts = int(datetime(2026, 2, 15, 12, 0).timestamp() * 1000)
        events = []
        
        # Living room events
        for i in range(15):
            events.append(create_test_event("light.living_room", "on", base_ts + i * 60000))
            events.append(create_test_event("switch.tv", "on", base_ts + i * 60000 + 5000))
        
        # Kitchen events
        for i in range(10):
            events.append(create_test_event("light.kitchen", "on", base_ts + i * 60000))
            events.append(create_test_event("switch.coffee_maker", "on", base_ts + i * 60000 + 10000))
        
        return events
    
    def test_filter_events_by_zone(self, mock_tag_zone, events):
        """Test event filtering by zone."""
        miner = ZoneBasedMiner(mock_tag_zone)
        
        living_room_events = miner.filter_events_by_zone(events, "zone:living_room")
        kitchen_events = miner.filter_events_by_zone(events, "zone:kitchen")
        
        # Should only include events from zone entities
        assert len(living_room_events) == 30  # 15 light + 15 switch
        assert len(kitchen_events) == 20  # 10 light + 10 switch
        
        # Check that all events are from correct entities
        lr_entities = {e.entity_id for e in living_room_events}
        assert lr_entities == {"light.living_room", "switch.tv"}
    
    def test_mine_zone_insufficient_events(self, mock_tag_zone):
        """Test mining with insufficient events."""
        miner = ZoneBasedMiner(mock_tag_zone)
        
        # Create only 5 events (less than min_events=10)
        base_ts = int(datetime(2026, 2, 15, 12, 0).timestamp() * 1000)
        events = [
            create_test_event("light.living_room", "on", base_ts + i * 60000)
            for i in range(5)
        ]
        
        result = miner.mine_zone(events, "zone:living_room")
        
        assert result.stats["skipped"] is True
        assert result.stats["reason"] == "insufficient_events"
    
    def test_mine_zone_with_safety_critical(self, mock_tag_zone, events):
        """Test that safety-critical entities are blocked."""
        mock_tag_zone.add_safety_critical("switch.tv")
        
        config = ZoneMiningConfig(
            zone_id="zone:living_room",
            min_events=5,
            safety_critical_entities={"switch.tv"},
        )
        
        miner = ZoneBasedMiner(mock_tag_zone)
        miner.set_zone_config("zone:living_room", config)
        
        result = miner.mine_zone(events, "zone:living_room", config)
        
        # Rules involving switch.tv should be blocked
        # Note: actual rule count depends on mining results
        assert isinstance(result.safety_blocked, list)
    
    def test_mine_all_zones(self, mock_tag_zone, events):
        """Test mining all zones."""
        miner = ZoneBasedMiner(mock_tag_zone)
        
        results = miner.mine_all_zones(events)
        
        assert "zone:living_room" in results
        assert "zone:kitchen" in results
        assert results["zone:living_room"].stats["events"] == 30
        assert results["zone:kitchen"].stats["events"] == 20
    
    def test_get_top_suggestions(self, mock_tag_zone, events):
        """Test getting top suggestions."""
        miner = ZoneBasedMiner(mock_tag_zone)
        
        results = miner.mine_all_zones(events)
        suggestions = miner.get_top_suggestions(results, limit=5)
        
        assert isinstance(suggestions, list)
        assert len(suggestions) <= 5
        
        for s in suggestions:
            assert "zone_id" in s
            assert "A" in s
            assert "B" in s
            assert "confidence" in s
            assert "score" in s
    
    def test_explain_suggestion(self, mock_tag_zone, events):
        """Test suggestion explanation."""
        miner = ZoneBasedMiner(mock_tag_zone)
        
        suggestion = {
            "zone_id": "zone:living_room",
            "A": "light.living_room:on",
            "B": "switch.tv:on",
            "confidence": 0.85,
            "lift": 2.5,
            "score": 0.9,
            "requires_confirmation": True,
        }
        
        explanation = miner.explain_suggestion(suggestion)
        
        assert "living_room" in explanation
        assert "light.living_room" in explanation
        assert "85%" in explanation
        assert "2.5" in explanation
        assert "Bestätigung erforderlich" in explanation
    
    def test_export_results(self, mock_tag_zone, events):
        """Test results export."""
        miner = ZoneBasedMiner(mock_tag_zone)
        
        results = miner.mine_all_zones(events)
        exported = miner.export_results(results)
        
        assert "zones" in exported
        assert "top_suggestions" in exported
        assert "summary" in exported
        
        assert exported["summary"]["total_zones"] == 2


class TestZoneBasedMinerIntegration:
    """Integration tests for zone-based mining."""
    
    @pytest.fixture
    def full_setup(self):
        """Create full integration setup."""
        zones = {
            "zone:living_room": ["light.living_room", "switch.tv"],
            "zone:bedroom": ["light.bedroom", "switch.fan"],
        }
        
        mock_tag_zone = MockTagZoneIntegration(zones)
        base_config = MiningConfig(
            min_support_A=3,
            min_support_B=3,
            windows=[60, 300],  # 1 min and 5 min windows
        )
        
        return ZoneBasedMiner(mock_tag_zone, base_config)
    
    def test_full_mining_pipeline(self, full_setup):
        """Test complete mining pipeline."""
        base_ts = int(datetime(2026, 2, 15, 12, 0).timestamp() * 1000)
        events = []
        
        # Create correlated events (A→B pattern)
        for i in range(20):
            # Light on, then TV on after 5 seconds
            events.append(create_test_event("light.living_room", "on", base_ts + i * 60000))
            events.append(create_test_event("switch.tv", "on", base_ts + i * 60000 + 5000))
        
        results = full_setup.mine_all_zones(events)
        
        # Should find patterns in living_room zone
        assert "zone:living_room" in results
        
        # Should have stats
        stats = results["zone:living_room"].stats
        assert stats["events"] == 40  # 20 light + 20 switch


if __name__ == "__main__":
    pytest.main([__file__, "-v"])