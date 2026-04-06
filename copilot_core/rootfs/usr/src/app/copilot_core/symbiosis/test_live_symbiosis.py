"""Symbiosis Live Test — End-to-End Test der symbiotischen Kette.
Testet: HA Event → Core Rule Engine → HA Service Call
"""
import asyncio
import logging
from copilot_core.symbiosis.rule_engine import SymbioticRuleEngine, ContextManager
from copilot_core.symbiosis.event_bus_sync import EventBusSync

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

async def test_full_symbiosis_chain():
    """Test the complete symbiosis chain."""
    _LOGGER.info("=== STARTING FULL SYMBIOSIS CHAIN TEST ===")
    
    # Initialize engines
    rule_engine = SymbioticRuleEngine()
    context_manager = ContextManager()
    
    # Register a test rule
    rule_id = rule_engine.register_rule(
        zone_id="zone.living_room",
        rule_type="presence",
        condition={
            "logic": "AND",
            "checks": [
                {"type": "presence", "payload": {"state": "on"}}
            ]
        },
        action={
            "type": "context_change",
            "context": "occupied",
            "priority": 5
        }
    )
    _LOGGER.info(f"Registered test rule: {rule_id}")
    
    # Simulate HA event
    test_event = {
        "event_type": "presence",
        "zone_id": "zone.living_room",
        "payload": {"state": "on", "entity_id": "binary_sensor.living_room_motion"}
    }
    
    # Evaluate rule
    zone_data = {"zone_id": "zone.living_room"}
    events = [test_event]
    
    actions = rule_engine.evaluate_zone(zone_data, events)
    _LOGGER.info(f"Rule evaluation returned {len(actions)} actions")
    
    # Execute action
    for action in actions:
        if action.get("type") == "context_change":
            result = context_manager.transition(
                zone_id="zone.living_room",
                new_context=action.get("context"),
                reason="rule_triggered"
            )
            _LOGGER.info(f"Context transition result: {result}")
    
    # Verify state
    final_context = context_manager.get_active_context("zone.living_room")
    _LOGGER.info(f"Final context: {final_context}")
    
    assert final_context == "occupied", f"Expected 'occupied', got '{final_context}'"
    _LOGGER.info("✅ FULL SYMBIOSIS CHAIN TEST PASSED")
    
    return {
        "test": "full_symbiosis_chain",
        "status": "passed",
        "rule_id": rule_id,
        "actions_executed": len(actions),
        "final_context": final_context
    }

if __name__ == "__main__":
    result = asyncio.run(test_full_symbiosis_chain())
    print(f"\nTest Result: {result}")
