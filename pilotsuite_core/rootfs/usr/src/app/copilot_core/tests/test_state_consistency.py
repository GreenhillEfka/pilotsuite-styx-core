"""Tests for State Consistency Manager (P2-006).

Tests state versioning, optimistic locking, conflict detection,
resolution strategies, and partition reconciliation.
"""
from __future__ import annotations

import pytest
import time
from copilot_core.state.consistency import (
    StateConsistencyManager,
    VersionedState,
    VectorClock,
    StateConflict,
    ConflictStrategy,
    ConsistencyLevel,
)


class TestVectorClock:
    """Tests for vector clock causality tracking."""
    
    def test_increment(self):
        """Test clock increment for a node."""
        clock = VectorClock()
        clock.increment("node-a")
        assert clock.clocks == {"node-a": 1}
        
        clock.increment("node-a")
        assert clock.clocks == {"node-a": 2}
        
        clock.increment("node-b")
        assert clock.clocks == {"node-a": 2, "node-b": 1}
    
    def test_merge(self):
        """Test merging two vector clocks."""
        clock_a = VectorClock({"node-a": 3, "node-b": 1})
        clock_b = VectorClock({"node-a": 1, "node-b": 5, "node-c": 2})
        
        clock_a.merge(clock_b)
        assert clock_a.clocks == {"node-a": 3, "node-b": 5, "node-c": 2}
    
    def test_happens_before(self):
        """Test happens-before relationship."""
        clock_a = VectorClock({"node-a": 1, "node-b": 2})
        clock_b = VectorClock({"node-a": 2, "node-b": 3})
        
        assert clock_a.happens_before(clock_b)
        assert not clock_b.happens_before(clock_a)
    
    def test_concurrent(self):
        """Test concurrent (incomparable) clocks."""
        clock_a = VectorClock({"node-a": 3, "node-b": 1})
        clock_b = VectorClock({"node-a": 1, "node-b": 3})
        
        assert clock_a.concurrent_with(clock_b)
        assert clock_b.concurrent_with(clock_a)
        assert not clock_a.happens_before(clock_b)
        assert not clock_b.happens_before(clock_a)
    
    def test_copy(self):
        """Test clock copy creates independent clone."""
        clock = VectorClock({"node-a": 5})
        copy = clock.copy()
        
        copy.increment("node-a")
        assert clock.clocks == {"node-a": 5}
        assert copy.clocks == {"node-a": 6}
    
    def test_to_from_dict(self):
        """Test serialization round-trip."""
        original = VectorClock({"node-a": 3, "node-b": 7})
        data = original.to_dict()
        restored = VectorClock.from_dict(data)
        
        assert restored.clocks == original.clocks
        assert restored is not original


class TestVersionedState:
    """Tests for versioned state wrapper."""
    
    def test_compute_checksum(self):
        """Test checksum computation is deterministic."""
        state = VersionedState(
            key="test.key",
            data={"value": 42, "name": "test"},
            version=1,
            vector_clock=VectorClock(),
            checksum="",
            updated_at=time.time(),
            node_id="node-a",
        )
        
        checksum1 = state.compute_checksum()
        checksum2 = state.compute_checksum()
        
        assert checksum1 == checksum2
        assert len(checksum1) == 16  # 16 hex chars
    
    def test_checksum_changes_with_data(self):
        """Test checksum changes when data changes."""
        state1 = VersionedState(
            key="test.key",
            data={"value": 42},
            version=1,
            vector_clock=VectorClock(),
            checksum="",
            updated_at=time.time(),
            node_id="node-a",
        )
        
        state2 = VersionedState(
            key="test.key",
            data={"value": 43},
            version=1,
            vector_clock=VectorClock(),
            checksum="",
            updated_at=time.time(),
            node_id="node-a",
        )
        
        assert state1.compute_checksum() != state2.compute_checksum()
    
    def test_to_from_dict(self):
        """Test serialization round-trip."""
        original = VersionedState(
            key="test.key",
            data={"value": 42},
            version=5,
            vector_clock=VectorClock({"node-a": 3}),
            checksum="abc123",
            updated_at=1234567890.0,
            node_id="node-a",
        )
        
        data = original.to_dict()
        restored = VersionedState.from_dict(data)
        
        assert restored.key == original.key
        assert restored.data == original.data
        assert restored.version == original.version
        assert restored.vector_clock.clocks == original.vector_clock.clocks
        assert restored.checksum == original.checksum
        assert restored.node_id == original.node_id


class TestStateConsistencyManager:
    """Tests for the main consistency manager."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh manager for each test."""
        return StateConsistencyManager(node_id="test-node")
    
    def test_initialization(self, manager):
        """Test manager initializes correctly."""
        status = manager.get_status()
        assert status["node_id"] == "test-node"
        assert status["consistency_level"] == "eventual"
        assert status["default_strategy"] == "last_write_wins"
        assert status["state_count"] == 0
        assert status["pending_conflicts"] == 0
    
    def test_update_state_new(self, manager):
        """Test creating a new state."""
        success, state, error = manager.update_state("zone.living", {"temp": 21.5})
        
        assert success is True
        assert error is None
        assert state.key == "zone.living"
        assert state.version == 1
        assert state.node_id == "test-node"
        assert state.data == {"temp": 21.5}
    
    def test_update_state_incremental(self, manager):
        """Test updating existing state increments version."""
        manager.update_state("zone.living", {"temp": 21.5})
        success, state, _ = manager.update_state("zone.living", {"temp": 22.0})
        
        assert success is True
        assert state.version == 2
    
    def test_optimistic_locking_success(self, manager):
        """Test successful optimistic lock."""
        manager.update_state("zone.living", {"temp": 21.5})
        success, state, error = manager.update_state(
            "zone.living", {"temp": 22.0}, expected_version=1
        )
        
        assert success is True
        assert state.version == 2
    
    def test_optimistic_locking_failure(self, manager):
        """Test optimistic lock failure on version mismatch."""
        manager.update_state("zone.living", {"temp": 21.5})
        success, state, error = manager.update_state(
            "zone.living", {"temp": 22.0}, expected_version=5
        )
        
        assert success is False
        assert state is None
        assert "Version mismatch" in error
    
    def test_force_update(self, manager):
        """Test force update bypasses version check."""
        manager.update_state("zone.living", {"temp": 21.5})
        state = manager.force_update_state("zone.living", {"temp": 22.0})
        
        assert state.version == 2
    
    def test_get_state(self, manager):
        """Test retrieving state."""
        manager.update_state("zone.living", {"temp": 21.5})
        state = manager.get_state("zone.living")
        
        assert state is not None
        assert state.key == "zone.living"
        assert state.data["temp"] == 21.5
    
    def test_get_state_missing(self, manager):
        """Test retrieving non-existent state."""
        state = manager.get_state("nonexistent")
        assert state is None
    
    def test_detect_conflict_concurrent_updates(self, manager):
        """Test detecting concurrent update conflicts."""
        # Create local state
        manager.update_state("zone.living", {"temp": 21.5})
        local = manager.get_state("zone.living")
        
        # Create concurrent remote state (different node, concurrent clock)
        remote = VersionedState(
            key="zone.living",
            data={"temp": 22.0},
            version=1,
            vector_clock=VectorClock({"remote-node": 1}),
            checksum="",
            updated_at=time.time(),
            node_id="remote-node",
        )
        remote.checksum = remote.compute_checksum()
        
        conflicts = manager.detect_conflicts({"zone.living": remote})
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type in ("concurrent_update", "checksum_mismatch")
    
    def test_detect_conflict_checksum_mismatch(self, manager):
        """Test detecting checksum mismatch conflicts."""
        manager.update_state("zone.living", {"temp": 21.5})
        local = manager.get_state("zone.living")
        
        # Same version, different data = checksum mismatch
        remote = VersionedState(
            key="zone.living",
            data={"temp": 22.0},
            version=1,
            vector_clock=local.vector_clock.copy(),
            checksum="different",
            updated_at=time.time(),
            node_id="remote-node",
        )
        
        conflicts = manager.detect_conflicts({"zone.living": remote})
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "checksum_mismatch"
    
    def test_resolve_last_write_wins(self, manager):
        """Test last-write-wins resolution."""
        manager.update_state("zone.living", {"temp": 21.5})
        local = manager.get_state("zone.living")
        
        # Remote state with later timestamp
        remote = VersionedState(
            key="zone.living",
            data={"temp": 22.0},
            version=1,
            vector_clock=VectorClock({"remote-node": 1}),
            checksum="",
            updated_at=time.time() + 100,  # Later
            node_id="remote-node",
        )
        remote.checksum = remote.compute_checksum()
        
        manager.detect_conflicts({"zone.living": remote})
        resolved = manager.resolve_conflict("zone.living", ConflictStrategy.LAST_WRITE_WINS)
        
        assert resolved is not None
        assert resolved.data["temp"] == 22.0  # Remote wins (later)
    
    def test_resolve_first_write_wins(self, manager):
        """Test first-write-wins resolution."""
        manager.update_state("zone.living", {"temp": 21.5})
        local = manager.get_state("zone.living")
        
        remote = VersionedState(
            key="zone.living",
            data={"temp": 22.0},
            version=1,
            vector_clock=VectorClock({"remote-node": 1}),
            checksum="",
            updated_at=time.time() + 100,
            node_id="remote-node",
        )
        remote.checksum = remote.compute_checksum()
        
        manager.detect_conflicts({"zone.living": remote})
        resolved = manager.resolve_conflict("zone.living", ConflictStrategy.FIRST_WRITE_WINS)
        
        assert resolved is not None
        assert resolved.data["temp"] == 21.5  # Local wins (earlier)
    
    def test_resolve_merge(self, manager):
        """Test merge resolution."""
        manager.update_state("zone.living", {"temp": 21.5, "humidity": 50})
        local = manager.get_state("zone.living")
        
        remote = VersionedState(
            key="zone.living",
            data={"temp": 22.0, "brightness": 80},
            version=1,
            vector_clock=VectorClock({"remote-node": 1}),
            checksum="",
            updated_at=time.time(),
            node_id="remote-node",
        )
        remote.checksum = remote.compute_checksum()
        
        manager.detect_conflicts({"zone.living": remote})
        resolved = manager.resolve_conflict("zone.living", ConflictStrategy.MERGE)
        
        assert resolved is not None
        # Merge: remote base + local override
        assert resolved.data["temp"] == 21.5  # Local override
        assert resolved.data["humidity"] == 50  # Local only
        assert resolved.data["brightness"] == 80  # Remote only
    
    def test_partition_reconciliation(self, manager):
        """Test partition reconciliation."""
        # Setup local state
        manager.update_state("zone.living", {"temp": 21.5})
        manager.update_state("zone.bedroom", {"temp": 20.0})
        
        # Start partition
        manager.start_partition(["node-b"])
        status = manager.get_status()
        assert status["in_partition"] is True
        
        # Simulate peer states during partition
        peer_states = {
            "node-b": {
                "zone.living": VersionedState(
                    key="zone.living",
                    data={"temp": 22.0},
                    version=1,
                    vector_clock=VectorClock({"node-b": 1}),
                    checksum="",
                    updated_at=time.time(),
                    node_id="node-b",
                ),
                "zone.kitchen": VersionedState(  # New state on peer
                    key="zone.kitchen",
                    data={"temp": 23.0},
                    version=1,
                    vector_clock=VectorClock({"node-b": 1}),
                    checksum="",
                    updated_at=time.time(),
                    node_id="node-b",
                ),
            }
        }
        for states in peer_states.values():
            for s in states.values():
                s.checksum = s.compute_checksum()
        
        # End partition and reconcile
        result = manager.end_partition(peer_states)
        
        assert result.conflicts_resolved >= 0
        assert "node-b" in result.nodes_synced
        assert len(result.reconciled_states) >= 2
        
        status = manager.get_status()
        assert status["in_partition"] is False
    
    def test_verify_consistency_linearizable(self, manager):
        """Test linearizable consistency verification."""
        manager.update_state("zone.living", {"temp": 21.5})
        local = manager.get_state("zone.living")
        
        # Consistent peer
        peer_states = {
            "node-b": {
                "zone.living": VersionedState(
                    key="zone.living",
                    data={"temp": 21.5},
                    version=1,
                    vector_clock=local.vector_clock.copy(),
                    checksum=local.checksum,
                    updated_at=local.updated_at,
                    node_id="node-b",
                ),
            }
        }
        
        report = manager.verify_consistency(peer_states, ConsistencyLevel.LINEARIZABLE)
        assert report["consistent"] is True
        assert len(report["inconsistencies"]) == 0
    
    def test_verify_consistency_inconsistent(self, manager):
        """Test detecting inconsistency."""
        manager.update_state("zone.living", {"temp": 21.5})
        
        # Inconsistent peer (different checksum)
        peer_states = {
            "node-b": {
                "zone.living": VersionedState(
                    key="zone.living",
                    data={"temp": 22.0},  # Different!
                    version=1,
                    vector_clock=VectorClock({"node-b": 1}),
                    checksum="",
                    updated_at=time.time(),
                    node_id="node-b",
                ),
            }
        }
        peer_states["node-b"]["zone.living"].checksum = "different"
        
        report = manager.verify_consistency(peer_states, ConsistencyLevel.LINEARIZABLE)
        assert report["consistent"] is False
        assert len(report["inconsistencies"]) > 0
    
    def test_custom_resolver(self, manager):
        """Test custom conflict resolver."""
        def custom_resolver(conflict: StateConflict) -> VersionedState:
            # Always prefer higher temperature
            if conflict.local_state.data.get("temp", 0) > conflict.remote_state.data.get("temp", 0):
                return conflict.local_state
            return conflict.remote_state
        
        manager.set_custom_resolver(custom_resolver)
        
        manager.update_state("zone.living", {"temp": 21.5})
        local = manager.get_state("zone.living")
        
        remote = VersionedState(
            key="zone.living",
            data={"temp": 22.0},
            version=1,
            vector_clock=VectorClock({"remote-node": 1}),
            checksum="",
            updated_at=time.time(),
            node_id="remote-node",
        )
        remote.checksum = remote.compute_checksum()
        
        manager.detect_conflicts({"zone.living": remote})
        resolved = manager.resolve_conflict("zone.living", ConflictStrategy.CUSTOM)
        
        assert resolved is not None
        assert resolved.data["temp"] == 22.0  # Higher temp wins
    
    def test_clear_state(self, manager):
        """Test clearing state."""
        manager.update_state("zone.living", {"temp": 21.5})
        manager.update_state("zone.bedroom", {"temp": 20.0})
        
        assert manager.get_state("zone.living") is not None
        
        manager.clear_state("zone.living")
        assert manager.get_state("zone.living") is None
        assert manager.get_state("zone.bedroom") is not None
        
        manager.clear_state()
        assert manager.get_state("zone.bedroom") is None


class TestConflictStrategy:
    """Tests for conflict strategy enum."""
    
    def test_strategy_values(self):
        """Test all strategy values exist."""
        assert ConflictStrategy.LAST_WRITE_WINS.value == "last_write_wins"
        assert ConflictStrategy.FIRST_WRITE_WINS.value == "first_write_wins"
        assert ConflictStrategy.MERGE.value == "merge"
        assert ConflictStrategy.CUSTOM.value == "custom"


class TestConsistencyLevel:
    """Tests for consistency level enum."""
    
    def test_level_values(self):
        """Test all level values exist."""
        assert ConsistencyLevel.EVENTUAL.value == "eventual"
        assert ConsistencyLevel.SEQUENTIAL.value == "sequential"
        assert ConsistencyLevel.LINEARIZABLE.value == "linearizable"
