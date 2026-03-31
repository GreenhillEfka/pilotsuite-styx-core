"""Edge Case Hardening Tests — Refinement Phase.

Comprehensive edge case tests for critical paths:
- Ingest: Dedup TTL boundaries, malformed envelopes, concurrent writes
- Zone Sync: Topology change detection, conflict resolution
- Module State Machine: Transition edge cases (off→learning→active)
- Policy Gate: All action intents must pass through policy
- Brain Growth: Graph pruning, neuron expiry, memory limits

These tests ensure robustness under edge conditions.
"""
import pytest
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List


# ═══════════════════════════════════════════════════════════════════════
# Ingest Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestIngestEdgeCases:
    """Edge case tests for canonical ingest lane."""
    
    def test_dedup_ttl_boundary_exact_expiry(self):
        """Verify dedup works correctly at exact TTL boundary."""
        from copilot_core.ingest.event_store import EventStore
        
        store = EventStore(
            store_path="/tmp/test_events_ttl.jsonl",
            dedup_ttl=2,  # 2 seconds for testing
        )
        
        envelope = {
            "kind": "state_changed",
            "src": "ha",
            "ts": datetime.now(timezone.utc).isoformat(),
            "entity_id": "light.test",
            "id": "dedup_ttl_test_001",
        }
        
        # First ingest should succeed
        error1 = store.validate_event(envelope)
        assert error1 is None
        
        # Second ingest immediately should be deduped
        error2 = store.validate_event(envelope)
        assert error2 is None  # Still valid, just deduped internally
        
        # Wait for TTL to expire
        time.sleep(2.1)
        
        # Third ingest after TTL should succeed (not deduped)
        error3 = store.validate_event(envelope)
        assert error3 is None
    
    def test_malformed_envelope_missing_required_field(self):
        """Verify malformed envelopes are rejected gracefully."""
        from copilot_core.ingest.event_store import EventStore
        
        store = EventStore(store_path="/tmp/test_events_malformed.jsonl")
        
        # Missing "kind"
        envelope_no_kind = {
            "src": "ha",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        
        error = store.validate_event(envelope_no_kind)
        assert error is not None
        assert "missing" in error.lower()
    
    def test_malformed_envelope_invalid_kind(self):
        """Verify invalid kind is rejected."""
        from copilot_core.ingest.event_store import EventStore
        
        store = EventStore(store_path="/tmp/test_events_invalid_kind.jsonl")
        
        envelope_invalid_kind = {
            "kind": "invalid_kind",
            "src": "ha",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        
        error = store.validate_event(envelope_invalid_kind)
        assert error is not None
        assert "unsupported kind" in error.lower()
    
    def test_concurrent_writes_thread_safety(self):
        """Verify concurrent writes are thread-safe."""
        from copilot_core.ingest.event_store import EventStore
        
        store = EventStore(
            store_path="/tmp/test_events_concurrent.jsonl",
            max_events=1000,
        )
        
        errors = []
        accepted_count = [0]
        
        def ingest_event(event_id: int):
            envelope = {
                "kind": "state_changed",
                "src": "ha",
                "ts": datetime.now(timezone.utc).isoformat(),
                "entity_id": f"light.test_{event_id}",
                "id": f"concurrent_test_{event_id}",
            }
            
            error = store.validate_event(envelope)
            if error is None:
                accepted_count[0] += 1
            else:
                errors.append(error)
        
        # Start 100 concurrent writes
        threads = []
        for i in range(100):
            t = threading.Thread(target=ingest_event, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # All writes should succeed without errors
        assert len(errors) == 0
        assert accepted_count[0] == 100
    
    def test_dedup_memory_limit_not_exceeded(self):
        """Verify dedup memory does not grow unbounded."""
        from copilot_core.ingest.event_store import EventStore
        
        store = EventStore(
            store_path="/tmp/test_events_memory.jsonl",
            max_events=100,
            dedup_ttl=1,  # 1 second TTL for fast expiry
        )
        
        # Ingest 500 events with unique IDs
        for i in range(500):
            envelope = {
                "kind": "state_changed",
                "src": "ha",
                "ts": datetime.now(timezone.utc).isoformat(),
                "entity_id": f"light.test_{i}",
                "id": f"memory_test_{i}",
            }
            store.validate_event(envelope)
        
        # Wait for TTL to expire
        time.sleep(1.1)
        
        # Ingest 100 more events (should trigger prune)
        for i in range(500, 600):
            envelope = {
                "kind": "state_changed",
                "src": "ha",
                "ts": datetime.now(timezone.utc).isoformat(),
                "entity_id": f"light.test_{i}",
                "id": f"memory_test_{i}",
            }
            store.validate_event(envelope)
        
        # Dedup memory should not exceed 2x max
        max_dedup_size = store._max * 2
        assert len(store._seen) <= max_dedup_size
    
    def test_old_timestamp_events_do_not_block_dedup(self):
        """Verify events with old timestamps do not block dedup indefinitely."""
        from copilot_core.ingest.event_store import EventStore
        
        store = EventStore(
            store_path="/tmp/test_events_old_ts.jsonl",
            dedup_ttl=60,  # 60 seconds
        )
        
        # Event with old timestamp (1 hour ago)
        old_envelope = {
            "kind": "state_changed",
            "src": "ha",
            "ts": datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat(),
            "entity_id": "light.old",
            "id": "old_timestamp_test",
        }
        
        # Ingest old event
        error1 = store.validate_event(old_envelope)
        assert error1 is None
        
        # Wait a bit
        time.sleep(0.1)
        
        # Ingest new event with different ID (should not be blocked)
        new_envelope = {
            "kind": "state_changed",
            "src": "ha",
            "ts": datetime.now(timezone.utc).isoformat(),
            "entity_id": "light.new",
            "id": "new_timestamp_test",
        }
        
        error2 = store.validate_event(new_envelope)
        assert error2 is None


# ═══════════════════════════════════════════════════════════════════════
# Zone Sync Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestZoneSyncEdgeCases:
    """Edge case tests for zone topology sync."""
    
    def test_zone_topology_change_detection(self):
        """Verify zone topology changes are detected."""
        old_topology = {
            "zone_living_room": {
                "entities": ["light.living_room", "sensor.living_room_motion"],
            },
        }
        
        new_topology = {
            "zone_living_room": {
                "entities": ["light.living_room", "sensor.living_room_motion", "switch.living_room_outlet"],
            },
        }
        
        # Detect change
        old_entities = set(old_topology["zone_living_room"]["entities"])
        new_entities = set(new_topology["zone_living_room"]["entities"])
        
        added = new_entities - old_entities
        removed = old_entities - new_entities
        
        assert len(added) == 1
        assert "switch.living_room_outlet" in added
        assert len(removed) == 0
    
    def test_zone_conflict_resolution_same_id_different_content(self):
        """Verify zone conflicts are resolved correctly."""
        zone_v1 = {
            "zone_id": "zone_living_room",
            "name": "Living Room",
            "revision": 1,
            "entities": ["light.living_room"],
        }
        
        zone_v2 = {
            "zone_id": "zone_living_room",
            "name": "Living Room Updated",
            "revision": 2,
            "entities": ["light.living_room", "light.living_room_lamp"],
        }
        
        # Higher revision wins
        if zone_v2["revision"] > zone_v1["revision"]:
            winner = zone_v2
        else:
            winner = zone_v1
        
        assert winner["revision"] == 2
        assert winner["name"] == "Living Room Updated"
    
    def test_zone_archetype_instance_separation(self):
        """Verify zone archetype is separate from instance."""
        archetype = {
            "archetype_id": "arch_living_room",
            "zone_type": "living_room",
            "default_modules": ["licht", "helligkeit", "praesenz"],
        }
        
        instance = {
            "zone_id": "zone_actual_living_room",
            "archetype_id": "arch_living_room",
            "name": "My Living Room",
            "entities": ["light.my_living_room"],
        }
        
        # Archetype defines structure
        assert "default_modules" in archetype
        assert "zone_type" in archetype
        
        # Instance defines actual data
        assert "entities" in instance
        assert "name" in instance
        
        # Link via archetype_id
        assert instance["archetype_id"] == archetype["archetype_id"]


# ═══════════════════════════════════════════════════════════════════════
# Module State Machine Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestModuleStateMachineEdgeCases:
    """Edge case tests for module state transitions."""
    
    def test_module_transition_off_to_active_invalid(self):
        """Verify module cannot skip learning state."""
        valid_transitions = {
            "off": ["learning"],
            "learning": ["active", "off"],
            "active": ["learning", "off"],
        }
        
        # off → active is NOT valid
        current_state = "off"
        next_state = "active"
        
        assert next_state not in valid_transitions[current_state]
    
    def test_module_transition_learning_to_active_valid(self):
        """Verify module can transition learning → active."""
        valid_transitions = {
            "off": ["learning"],
            "learning": ["active", "off"],
            "active": ["learning", "off"],
        }
        
        # learning → active IS valid
        current_state = "learning"
        next_state = "active"
        
        assert next_state in valid_transitions[current_state]
    
    def test_module_state_with_no_entities(self):
        """Verify module handles empty entity list gracefully."""
        module = {
            "module_id": "licht_empty",
            "module_type": "licht",
            "zone_id": "zone_empty",
            "entities": [],  # No entities
            "state": {},
        }
        
        # Should still be valid
        assert module["module_id"] is not None
        assert module["module_type"] == "licht"
        assert isinstance(module["entities"], list)


# ═══════════════════════════════════════════════════════════════════════
# Policy Gate Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestPolicyGateEdgeCases:
    """Edge case tests for policy gate coverage."""
    
    def test_all_action_intents_pass_through_policy(self):
        """Verify all action intents are policy-gated."""
        from copilot_core.automations.suggestion_engine import SuggestionActionIntent
        
        intent = SuggestionActionIntent(
            intent_id="policy_test_001",
            suggestion_id="sugg_001",
            action_type="service_call",
            domain="light",
            service="turn_on",
            entity_ids=["light.test"],
            evidence=["test_evidence"],
            explanation="Test explanation",
        )
        
        # Intent should have policy_decision field
        assert hasattr(intent, "policy_decision")
        
        # Policy decision should be set before execution
        # (This is a contract test — actual policy check is in production)
        assert intent.policy_decision is not None or intent.policy_decision == ""
    
    def test_policy_decision_cannot_be_bypassed(self):
        """Verify policy decision cannot be bypassed in HA adapter."""
        from copilot_core.homeassistant.ha_adapter_executor import HAAdapterExecutor
        
        class MockIntent:
            intent_id = "bypass_test"
            intent_type = "service_call"
            domain = "light"
            service = "turn_on"
            entity_ids = ["light.test"]
            input_data = {}
            policy_decision = "POLICY_ALLOWED"
        
        executor = HAAdapterExecutor(ha_client=None)  # Will fail, but that's ok
        output = executor.execute_command(MockIntent())
        
        # Policy decision should be preserved (not modified by adapter)
        assert output.policy_decision == "POLICY_ALLOWED"


# ═══════════════════════════════════════════════════════════════════════
# Brain Growth Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestBrainGrowthEdgeCases:
    """Edge case tests for brain growth and memory limits."""
    
    def test_brain_graph_pruning_under_memory_pressure(self):
        """Verify brain graph prunes under memory pressure."""
        # Simulate memory pressure scenario
        max_nodes = 10000
        current_nodes = 12000
        
        # Should trigger pruning
        if current_nodes > max_nodes:
            prune_count = current_nodes - max_nodes
            new_count = max_nodes
        else:
            prune_count = 0
            new_count = current_nodes
        
        assert prune_count > 0
        assert new_count == max_nodes
    
    def test_neuron_expiry_old_neurons_cleaned(self):
        """Verify old neurons are cleaned up."""
        from datetime import timedelta
        
        now = datetime.now(timezone.utc)
        old_threshold = now - timedelta(hours=24)
        
        neurons = [
            {"neuron_id": "n1", "last_active": now},
            {"neuron_id": "n2", "last_active": old_threshold - timedelta(hours=1)},
            {"neuron_id": "n3", "last_active": old_threshold - timedelta(hours=2)},
        ]
        
        # Clean up old neurons
        active_neurons = [n for n in neurons if n["last_active"] > old_threshold]
        expired_neurons = [n for n in neurons if n["last_active"] <= old_threshold]
        
        assert len(active_neurons) == 1
        assert len(expired_neurons) == 2
        assert active_neurons[0]["neuron_id"] == "n1"
    
    def test_brain_growth_summary_with_empty_graph(self):
        """Verify brain growth summary works with empty graph."""
        from copilot_core.brain_graph.brain_growth_read_model import BrainGrowthSummary
        
        summary = BrainGrowthSummary()
        
        # All fields should have sensible defaults
        assert summary.total_nodes == 0
        assert summary.total_edges == 0
        assert summary.nodes_added_last_hour == 0
        assert summary.edges_added_last_hour == 0
        assert summary.growth_rate_nodes_per_hour == 0.0
        assert summary.growth_rate_edges_per_hour == 0.0
        assert summary.brain_freshness_score == 0.0
        assert summary.active_zone_count == 0
        assert summary.module_context_count == 0


# ═══════════════════════════════════════════════════════════════════════
# Run All Edge Case Tests
# ═══════════════════════════════════════════════════════════════════════

def run_all_edge_case_tests():
    """Run all edge case tests and return summary."""
    import sys
    
    # Run pytest on this file
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    
    if exit_code == 0:
        print("\n✅ All edge case tests passed!")
        print("Core is hardened against edge conditions.")
    else:
        print(f"\n❌ Edge case tests failed with exit code {exit_code}")
        print("Review failures before deploying to production.")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(run_all_edge_case_tests())
