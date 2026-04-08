"""Tests for Habitus Miner module."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from copilot_core.habitus_miner.model import NormEvent, MiningConfig
from copilot_core.habitus_miner.service import HabitusMinerService
from copilot_core.habitus_miner.mining import mine_ab_rules


def create_test_events():
    """Create test event stream for mining."""
    base_time = int(datetime.now().timestamp() * 1000)
    events = []
    
    # Pattern: light.kitchen:on -> switch.fan:on (within 30s)
    for i in range(25):
        # Light on
        events.append(NormEvent(
            ts=base_time + i * 3600000,  # Every hour
            key="light.kitchen:on",
            entity_id="light.kitchen",
            domain="light",
            transition=":on",
            context={"source": "manual", "time_of_day": "evening"}
        ))
        
        # Fan on 10-20 seconds later (most of the time)
        if i < 20:  # 80% success rate
            events.append(NormEvent(
                ts=base_time + i * 3600000 + 15000,  # 15s later
                key="switch.fan:on",
                entity_id="switch.fan",
                domain="switch",
                transition=":on",
                context={"source": "manual", "time_of_day": "evening"}
            ))
    
    # Add some noise events
    for i in range(10):
        events.append(NormEvent(
            ts=base_time + i * 1800000,  # Every 30 minutes
            key="sensor.temp:22",
            entity_id="sensor.temp",
            domain="sensor", 
            transition=":22",
            context={"source": "device"}
        ))
    
    return events


def test_norm_event_creation():
    """Test NormEvent creation and key formatting."""
    event = NormEvent(
        ts=1640995200000,
        key="light.test",  # Should be auto-formatted
        entity_id="light.test",
        domain="light",
        transition="on"
    )
    
    assert event.key == "light.test:on"


def test_mining_config_defaults():
    """Test MiningConfig default values."""
    config = MiningConfig()
    
    assert config.windows == [30, 120, 600, 3600]
    assert config.min_support_A == 20
    assert config.min_hits == 10
    assert config.min_confidence == 0.5
    assert config.exclude_self_rules is True


def test_basic_rule_mining():
    """Test basic A→B rule mining."""
    events = create_test_events()
    config = MiningConfig(
        min_support_A=10,
        min_hits=5,
        min_confidence=0.3,
        min_lift=1.1,
        max_rules=50
    )
    
    rules = mine_ab_rules(events, config)
    
    # Should find the light -> fan pattern
    assert len(rules) > 0
    
    # Find our expected rule
    kitchen_fan_rule = None
    for rule in rules:
        if "light.kitchen:on" in rule.A and "switch.fan:on" in rule.B:
            kitchen_fan_rule = rule
            break
    
    assert kitchen_fan_rule is not None
    assert kitchen_fan_rule.confidence > 0.7  # 80% success rate
    assert kitchen_fan_rule.nA >= 20  # Should have enough support
    assert kitchen_fan_rule.nAB >= 15  # Should have enough hits


def test_service_ha_event_normalization():
    """Test Home Assistant event normalization."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        service = HabitusMinerService(Path(tmp_dir))
        
        # Test HA state_changed event
        ha_event = {
            "time_fired": "2026-02-09T18:00:00Z",
            "event_type": "state_changed",
            "data": {
                "entity_id": "light.bedroom",
                "old_state": {"state": "off"},
                "new_state": {"state": "on"},
            },
            "context": {"source": "manual"}
        }
        
        norm_event = service.normalize_ha_event(ha_event)
        
        assert norm_event is not None
        assert norm_event.entity_id == "light.bedroom"
        assert norm_event.domain == "light"
        assert norm_event.transition == ":on"
        assert norm_event.key == "light.bedroom:on"
        assert norm_event.context["source"] == "manual"


def test_service_filtering():
    """Test event filtering and deduplication."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = MiningConfig(
            exclude_domains=["sensor"],
            default_cooldown=5,
        )
        service = HabitusMinerService(Path(tmp_dir), config)
        
        events = create_test_events()
        
        # Test filtering - should remove sensor events
        rules = service.mine_rules(events)
        
        # Should still find light->fan pattern but no sensor rules
        sensor_rules = [r for r in rules if "sensor" in r.A or "sensor" in r.B]
        assert len(sensor_rules) == 0


def test_rule_explanation():
    """Test rule explanation generation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        service = HabitusMinerService(Path(tmp_dir))
        events = create_test_events()
        
        rules = service.mine_rules(events)
        
        if rules:
            explanation = service.explain_rule(rules[0])
            
            assert "rule_summary" in explanation
            assert "confidence" in explanation
            assert "evidence" in explanation
            assert "percentage" in explanation["confidence"]


def test_rules_persistence():
    """Test rule storage and retrieval."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        service = HabitusMinerService(Path(tmp_dir))
        events = create_test_events()
        
        # Mine rules
        rules = service.mine_rules(events)
        initial_count = len(rules)
        
        # Create new service instance (simulates restart)
        service2 = HabitusMinerService(Path(tmp_dir))
        stored_rules = service2.get_rules()
        
        assert len(stored_rules) == initial_count
        
        if stored_rules:
            assert stored_rules[0].A == rules[0].A
            assert stored_rules[0].B == rules[0].B
            assert stored_rules[0].confidence == rules[0].confidence


def test_export_summary():
    """Test rules summary export."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        service = HabitusMinerService(Path(tmp_dir))
        events = create_test_events()
        
        rules = service.mine_rules(events)
        summary = service.export_rules_summary(rules)
        
        assert "total_rules" in summary
        assert "top_rules" in summary
        assert "domain_patterns" in summary
        assert summary["total_rules"] == len(rules)
        
        if rules:
            assert len(summary["top_rules"]) > 0
            assert "A" in summary["top_rules"][0]
            assert "confidence" in summary["top_rules"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])