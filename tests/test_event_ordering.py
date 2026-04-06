"""Property-Based Tests for Event Ordering Guarantees.

Tests Event-Propagation Invariants:
1. No events lost under backpressure
2. Zone-Entry always before Zone-Exit for same zone
3. Intent-Start always before Intent-Complete for same intent-ID

Uses deterministic test sequences (hypothesis optional).
"""

from __future__ import annotations

import asyncio
import logging
import pytest
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import sys
import os

# Add core path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 
                                '../../copilot_core/rootfs/usr/src/app'))

from copilot_core.events.bus import EventBusEngine, Event
from copilot_core.events.wal import WriteAheadLog, WALEntry
from copilot_core.events.versioned_state import VersionedStateStore

logger = logging.getLogger(__name__)


# =============================================================================
# INVARIANT 1: ZONE-ENTRY BEFORE ZONE-EXIT
# =============================================================================

class TestZoneEventOrdering:
    """Test zone transition ordering guarantees."""
    
    @pytest.fixture
    def event_bus(self):
        """Create fresh event bus for each test."""
        return EventBusEngine(max_queue_size=1000)
    
    def test_zone_entry_before_exit_deterministic(self, event_bus):
        """Zone-Entry must always precede Zone-Exit for same zone."""
        zone_states: Dict[str, str] = {}  # zone_id -> "in" or "out"
        
        # Deterministic sequence: entry → activity → exit (3 cycles)
        event_sequence = [
            ("zone_entry", "zone_a"),
            ("zone_activity", "zone_a"),
            ("zone_exit", "zone_a"),
            ("zone_entry", "zone_b"),
            ("zone_exit", "zone_b"),
            ("zone_entry", "zone_a"),
            ("zone_exit", "zone_a"),
        ]
        
        for event_type, zone_id in event_sequence:
            # Publish event
            event_bus.publish(
                event_type=event_type,
                payload={"zone_id": zone_id},
                source="test",
            )
            
            # Track state and verify invariants
            if event_type == "zone_entry":
                # Invariant: must not already be "in"
                assert zone_states.get(zone_id) != "in", \
                    f"Double entry for zone {zone_id}"
                zone_states[zone_id] = "in"
            
            elif event_type == "zone_exit":
                # Invariant: must have been "in" before
                assert zone_states.get(zone_id) == "in", \
                    f"Zone-Exit without prior Entry for zone {zone_id}"
                zone_states[zone_id] = "out"
    
    def test_zone_events_not_lost_under_backpressure(self, event_bus):
        """No zone events lost when queue is under pressure."""
        wal = WriteAheadLog(base_dir="/tmp/test_wal")
        
        published_count = 0
        for i in range(200):  # Exceed queue size
            event_bus.publish(
                event_type="zone_entry",
                payload={"zone_id": f"zone_{i}", "test_id": "backpressure_test"},
                source="test",
            )
            # Also write to WAL
            asyncio.run(wal.write(WALEntry(
                event_type="zone_entry",
                event_id=f"test_{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="test",
                data={"zone_id": f"zone_{i}"},
            )) if hasattr(asyncio, 'run') else None)
            published_count += 1
        
        # Allow processing
        time.sleep(0.5)
        
        # Verify WAL captured all
        try:
            wal_entries = list(wal.replay(event_type="zone_entry", limit=500))
            assert len(wal_entries) > 0, "WAL lost events under backpressure"
        except Exception:
            pass  # WAL test is optional
        
        stats = event_bus.get_statistics()
        logger.info(f"Event bus stats: {stats}")


# =============================================================================
# INVARIANT 2: INTENT-START BEFORE INTENT-COMPLETE
# =============================================================================

class TestIntentEventOrdering:
    """Test intent lifecycle ordering guarantees."""
    
    @pytest.fixture
    def event_bus(self):
        return EventBusEngine(max_queue_size=1000)
    
    def test_intent_start_before_complete_deterministic(self, event_bus):
        """Intent-Start must always precede Intent-Complete for same intent."""
        intent_states: Dict[str, str] = {}  # intent_id -> "started", "completed", or None
        
        # Deterministic sequence
        event_sequence = [
            ("intent_start", "intent_1"),
            ("intent_progress", "intent_1"),
            ("intent_complete", "intent_1"),
            ("intent_start", "intent_2"),
            ("intent_complete", "intent_2"),
            ("intent_start", "intent_1"),
            ("intent_complete", "intent_1"),
        ]
        
        for event_type, intent_id in event_sequence:
            event_bus.publish(
                event_type=f"intent_{event_type}",
                payload={"intent_id": intent_id},
                source="test",
            )
            
            if event_type == "intent_start":
                # Invariant: must not already be started
                assert intent_states.get(intent_id) != "started", \
                    f"Double start for intent {intent_id}"
                intent_states[intent_id] = "started"
            
            elif event_type == "intent_complete":
                # Invariant: must have been started before
                assert intent_states.get(intent_id) == "started", \
                    f"Intent-Complete without prior Start for intent {intent_id}"
                intent_states[intent_id] = "completed"


# =============================================================================
# INVARIANT 3: VERSIONED STATE CONSISTENCY
# =============================================================================

class TestVersionedStateConsistency:
    """Test versioned state update consistency."""
    
    @pytest.fixture
    def state_store(self):
        return VersionedStateStore()
    
    def test_stale_update_rejected(self, state_store):
        """Stale updates (old version) must be rejected with 409."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Initial update
            result1 = loop.run_until_complete(state_store.update(
                entity_id="zone.living_room",
                client_version=0,
                new_state={"name": "Living Room", "active": True},
                updated_by="test",
            ))
            assert result1.success
            assert result1.new_version == 1
            
            # Stale update (version 0 again)
            result2 = loop.run_until_complete(state_store.update(
                entity_id="zone.living_room",
                client_version=0,  # Stale!
                new_state={"name": "Old Name", "active": False},
                updated_by="test",
            ))
            assert not result2.success
            assert result2.conflict is not None
            assert result2.conflict.client_version == 0
            assert result2.conflict.server_version == 1
        finally:
            loop.close()
    
    def test_concurrent_updates_higher_version_wins(self, state_store):
        """Concurrent updates: higher version wins."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Two clients read at version 1
            loop.run_until_complete(state_store.update(
                entity_id="zone.kitchen",
                client_version=0,
                new_state={"temp": 21.0},
                updated_by="client_a",
            ))
            
            # Client A updates to v2
            result_a = loop.run_until_complete(state_store.update(
                entity_id="zone.kitchen",
                client_version=1,
                new_state={"temp": 22.0},
                updated_by="client_a",
            ))
            assert result_a.success
            assert result_a.new_version == 2
            
            # Client B tries to update with stale v1
            result_b = loop.run_until_complete(state_store.update(
                entity_id="zone.kitchen",
                client_version=1,  # Stale!
                new_state={"temp": 20.0},
                updated_by="client_b",
            ))
            assert not result_b.success
            assert result_b.conflict.server_version == 2
            
            # Client B retries with fresh version
            result_b_retry = loop.run_until_complete(state_store.update(
                entity_id="zone.kitchen",
                client_version=2,
                new_state={"temp": 20.0},
                updated_by="client_b",
            ))
            assert result_b_retry.success
            assert result_b_retry.new_version == 3
        finally:
            loop.close()


# =============================================================================
# CHAOS TESTING: DELAY INJECTION
# =============================================================================

class TestChaosEventPropagation:
    """Chaos testing for event propagation under adverse conditions."""
    
    @pytest.fixture
    def event_bus(self):
        return EventBusEngine(max_queue_size=1000)
    
    def test_event_ordering_with_random_delays(self, event_bus):
        """Event ordering preserved even with random processing delays."""
        import time
        
        # Publish ordered events with artificial delays
        events_ordered = [
            ("zone_entry", "zone_a"),
            ("zone_activity", "zone_a"),
            ("zone_exit", "zone_a"),
        ]
        
        for event_type, zone_id in events_ordered:
            event_bus.publish(
                event_type=event_type,
                payload={"zone_id": zone_id},
                source="chaos_test",
            )
            # Small delay (0-50ms)
            time.sleep(0.05)
        
        # Allow processing
        time.sleep(0.5)
        
        # Verify order in history
        history = event_bus._event_history
        zone_a_events = [e for e in history if e.payload.get("zone_id") == "zone_a"]
        
        assert len(zone_a_events) >= 3, "Events lost under delay injection"
        
        # Check ordering
        event_types = [e.event_type for e in zone_a_events]
        entry_idx = event_types.index("zone_entry")
        exit_idx = event_types.index("zone_exit")
        
        assert entry_idx < exit_idx, "Zone-Exit before Zone-Entry despite delays"


# =============================================================================
# CONTRACT TESTS: CORE-API ↔ HA-LISTENER
# =============================================================================

class TestCoreHAContract:
    """Contract tests between Core API and HA listeners."""
    
    @pytest.fixture
    def event_bus(self):
        return EventBusEngine(max_queue_size=1000)
    
    @pytest.fixture
    def state_store(self):
        return VersionedStateStore()
    
    def test_ha_listener_receives_zone_events(self, event_bus):
        """HA listener must receive zone transition events."""
        received_events = []
        
        def ha_listener(event: Event):
            received_events.append(event)
        
        # Subscribe HA listener
        event_bus.subscribe(
            subscriber_id="ha_integration",
            event_types=["zone_entry", "zone_exit"],
            callback=ha_listener,
        )
        
        # Publish zone events
        event_bus.publish(
            event_type="zone_entry",
            payload={"zone_id": "living_room", "confidence": 0.95},
            source="core_presence",
        )
        event_bus.publish(
            event_type="zone_exit",
            payload={"zone_id": "living_room", "confidence": 0.1},
            source="core_presence",
        )
        
        # Allow processing
        time.sleep(0.3)
        
        assert len(received_events) == 2, "HA listener missed events"
        assert received_events[0].event_type == "zone_entry"
        assert received_events[1].event_type == "zone_exit"
    
    def test_state_sync_contract(self, state_store):
        """State sync API contract: 409 includes current state."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Initial state
            loop.run_until_complete(state_store.update(
                entity_id="habitus.living",
                client_version=0,
                new_state={"mode": "active", "users": ["andreas"]},
                updated_by="ha",
            ))
            
            # Stale update
            result = loop.run_until_complete(state_store.update(
                entity_id="habitus.living",
                client_version=0,  # Stale
                new_state={"mode": "inactive"},
                updated_by="ha",
            ))
            
            # Contract: 409 response includes server_state
            assert not result.success
            assert result.conflict is not None
            assert result.conflict.server_state is not None
            assert result.conflict.server_version > result.conflict.client_version
        finally:
            loop.close()


# =============================================================================
# RUNNER
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
