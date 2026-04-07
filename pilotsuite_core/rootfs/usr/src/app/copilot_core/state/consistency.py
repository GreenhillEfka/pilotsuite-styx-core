"""State Consistency Checks (P2-006).

Provides state versioning, optimistic locking, conflict detection and resolution,
and state reconciliation after network partitions.

Features:
- State versioning with vector clocks
- Optimistic locking for concurrent updates
- Conflict detection and resolution strategies
- State reconciliation after network partitions
- Consistency verification endpoints

Usage:
    from copilot_core.state.consistency import StateConsistencyManager
    
    manager = StateConsistencyManager()
    
    # Versioned state update
    success = manager.update_state("zone.living_room", new_data, expected_version=5)
    
    # Check for conflicts
    conflicts = manager.detect_conflicts()
    
    # Reconcile after partition
    result = manager.reconcile_partition(local_state, remote_state)
"""
from __future__ import annotations

import logging
import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

_LOGGER = logging.getLogger(__name__)


class ConflictStrategy(Enum):
    """Resolution strategies for state conflicts."""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MERGE = "merge"
    CUSTOM = "custom"


class ConsistencyLevel(Enum):
    """Consistency levels for state operations."""
    EVENTUAL = "eventual"
    SEQUENTIAL = "sequential"
    LINEARIZABLE = "linearizable"


@dataclass
class VectorClock:
    """Vector clock for tracking causality across nodes.
    
    Each node maintains a vector of logical timestamps, one per node.
    Used to detect concurrent modifications and establish happens-before order.
    """
    clocks: Dict[str, int] = field(default_factory=dict)
    
    def increment(self, node_id: str) -> None:
        """Increment the clock for a specific node."""
        self.clocks[node_id] = self.clocks.get(node_id, 0) + 1
    
    def merge(self, other: "VectorClock") -> None:
        """Merge with another vector clock (take max of each component)."""
        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())
        for node in all_nodes:
            self.clocks[node] = max(
                self.clocks.get(node, 0),
                other.clocks.get(node, 0)
            )
    
    def happens_before(self, other: "VectorClock") -> bool:
        """Check if this clock happens-before another.
        
        A happens-before B if all components of A are <= B and at least one is <.
        """
        all_less_or_equal = all(
            self.clocks.get(n, 0) <= other.clocks.get(n, 0)
            for n in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        at_least_one_less = any(
            self.clocks.get(n, 0) < other.clocks.get(n, 0)
            for n in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        return all_less_or_equal and at_least_one_less
    
    def concurrent_with(self, other: "VectorClock") -> bool:
        """Check if this clock is concurrent with another (neither happens-before)."""
        return not self.happens_before(other) and not other.happens_before(self)
    
    def copy(self) -> "VectorClock":
        """Create a copy of this vector clock."""
        return VectorClock(clocks=dict(self.clocks))
    
    def to_dict(self) -> Dict[str, int]:
        return dict(self.clocks)
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "VectorClock":
        return cls(clocks=dict(data))


@dataclass
class VersionedState:
    """State wrapper with versioning metadata."""
    key: str
    data: Dict[str, Any]
    version: int
    vector_clock: VectorClock
    checksum: str
    updated_at: float
    node_id: str
    
    def compute_checksum(self) -> str:
        """Compute SHA256 checksum of state data."""
        import json
        canonical = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "data": self.data,
            "version": self.version,
            "vector_clock": self.vector_clock.to_dict(),
            "checksum": self.checksum,
            "updated_at": self.updated_at,
            "node_id": self.node_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionedState":
        return cls(
            key=data["key"],
            data=data["data"],
            version=data["version"],
            vector_clock=VectorClock.from_dict(data["vector_clock"]),
            checksum=data["checksum"],
            updated_at=data["updated_at"],
            node_id=data["node_id"],
        )


@dataclass
class StateConflict:
    """Represents a detected state conflict."""
    key: str
    local_state: VersionedState
    remote_state: VersionedState
    conflict_type: str  # "version_mismatch" | "concurrent_update" | "checksum_mismatch"
    detected_at: float
    resolution: Optional[str] = None
    resolved_state: Optional[VersionedState] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "conflict_type": self.conflict_type,
            "local_version": self.local_state.version,
            "remote_version": self.remote_state.version,
            "local_checksum": self.local_state.checksum,
            "remote_checksum": self.remote_state.checksum,
            "detected_at": self.detected_at,
            "resolution": self.resolution,
            "resolved": self.resolved_state is not None,
        }


@dataclass
class ReconciliationResult:
    """Result of state reconciliation after partition."""
    reconciled_states: List[VersionedState]
    conflicts_resolved: int
    conflicts_unresolved: int
    partition_duration_ms: float
    nodes_synced: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reconciled_count": len(self.reconciled_states),
            "conflicts_resolved": self.conflicts_resolved,
            "conflicts_unresolved": self.conflicts_unresolved,
            "partition_duration_ms": self.partition_duration_ms,
            "nodes_synced": self.nodes_synced,
        }


class StateConsistencyManager:
    """Manages state consistency across distributed nodes.
    
    Features:
    - Optimistic locking with version checks
    - Vector clocks for causality tracking
    - Conflict detection and resolution
    - Partition reconciliation
    - Consistency verification
    """
    
    def __init__(
        self,
        node_id: Optional[str] = None,
        consistency_level: ConsistencyLevel = ConsistencyLevel.EVENTUAL,
        default_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
    ):
        self.node_id = node_id or self._generate_node_id()
        self.consistency_level = consistency_level
        self.default_strategy = default_strategy
        
        # Local state store: key -> VersionedState
        self._state_store: Dict[str, VersionedState] = {}
        
        # Pending conflicts: key -> StateConflict
        self._conflicts: Dict[str, StateConflict] = {}
        
        # Partition tracking
        self._partition_start: Optional[float] = None
        self._partition_peers: List[str] = []
        
        # Custom conflict resolver callback
        self._custom_resolver: Optional[callable] = None
        
        _LOGGER.info("StateConsistencyManager initialized (node=%s, level=%s)", 
                     self.node_id, self.consistency_level.value)
    
    def _generate_node_id(self) -> str:
        """Generate a unique node identifier."""
        import os
        import socket
        hostname = socket.gethostname()
        pid = os.getpid()
        return f"{hostname}-{pid}"
    
    def get_state(self, key: str) -> Optional[VersionedState]:
        """Get current state for a key."""
        return self._state_store.get(key)
    
    def get_all_states(self) -> Dict[str, VersionedState]:
        """Get all tracked states."""
        return dict(self._state_store)
    
    def update_state(
        self,
        key: str,
        new_data: Dict[str, Any],
        expected_version: Optional[int] = None,
    ) -> Tuple[bool, Optional[VersionedState], Optional[str]]:
        """Update state with optimistic locking.
        
        Args:
            key: State key
            new_data: New state data
            expected_version: Expected version for optimistic locking (None = force)
        
        Returns:
            Tuple of (success, new_state, error_message)
        """
        current_time = time.time()
        
        if key in self._state_store:
            current = self._state_store[key]
            
            # Optimistic locking check
            if expected_version is not None and current.version != expected_version:
                error_msg = (
                    f"Version mismatch for {key}: expected {expected_version}, "
                    f"got {current.version}"
                )
                _LOGGER.warning("Optimistic lock failed: %s", error_msg)
                return False, None, error_msg
            
            # Create new versioned state
            new_version = current.version + 1
            vector_clock = current.vector_clock.copy()
        else:
            # New state
            new_version = 1
            vector_clock = VectorClock()
        
        # Increment our node's clock
        vector_clock.increment(self.node_id)
        
        new_state = VersionedState(
            key=key,
            data=dict(new_data),
            version=new_version,
            vector_clock=vector_clock,
            checksum="",  # Will be computed
            updated_at=current_time,
            node_id=self.node_id,
        )
        new_state.checksum = new_state.compute_checksum()
        
        self._state_store[key] = new_state
        _LOGGER.debug("State updated: %s (version=%d)", key, new_version)
        
        return True, new_state, None
    
    def force_update_state(
        self,
        key: str,
        new_data: Dict[str, Any],
    ) -> VersionedState:
        """Force update state without version check (use with caution)."""
        success, state, _ = self.update_state(key, new_data, expected_version=None)
        return state
    
    def detect_conflicts(
        self,
        remote_states: Dict[str, VersionedState],
    ) -> List[StateConflict]:
        """Detect conflicts between local and remote states.
        
        Args:
            remote_states: States from another node
        
        Returns:
            List of detected conflicts
        """
        conflicts = []
        current_time = time.time()
        
        # Check all local states against remote
        for key, local_state in self._state_store.items():
            if key not in remote_states:
                continue
            
            remote_state = remote_states[key]
            conflict = self._check_conflict(local_state, remote_state, current_time)
            if conflict:
                conflicts.append(conflict)
                self._conflicts[key] = conflict
        
        # Check for states only in remote
        for key, remote_state in remote_states.items():
            if key not in self._state_store:
                # Not a conflict, just missing state - will be synced
                pass
        
        _LOGGER.info("Detected %d conflict(s) in %d state(s)", len(conflicts), len(self._state_store))
        return conflicts
    
    def _check_conflict(
        self,
        local: VersionedState,
        remote: VersionedState,
        timestamp: float,
    ) -> Optional[StateConflict]:
        """Check if two states are in conflict."""
        # Checksum mismatch with same version = corruption
        if local.version == remote.version and local.checksum != remote.checksum:
            return StateConflict(
                key=local.key,
                local_state=local,
                remote_state=remote,
                conflict_type="checksum_mismatch",
                detected_at=timestamp,
            )
        
        # Different versions - check vector clocks for concurrency
        if local.version != remote.version:
            if local.vector_clock.concurrent_with(remote.vector_clock):
                return StateConflict(
                    key=local.key,
                    local_state=local,
                    remote_state=remote,
                    conflict_type="concurrent_update",
                    detected_at=timestamp,
                )
        
        return None
    
    def resolve_conflict(
        self,
        key: str,
        strategy: Optional[ConflictStrategy] = None,
    ) -> Optional[VersionedState]:
        """Resolve a detected conflict.
        
        Args:
            key: State key with conflict
            strategy: Resolution strategy (uses default if None)
        
        Returns:
            Resolved state, or None if no conflict exists
        """
        if key not in self._conflicts:
            _LOGGER.debug("No conflict to resolve for %s", key)
            return None
        
        conflict = self._conflicts[key]
        strategy = strategy or self.default_strategy
        
        _LOGGER.info("Resolving conflict for %s with strategy %s", key, strategy.value)
        
        resolved = None
        if strategy == ConflictStrategy.LAST_WRITE_WINS:
            resolved = self._resolve_last_write_wins(conflict)
        elif strategy == ConflictStrategy.FIRST_WRITE_WINS:
            resolved = self._resolve_first_write_wins(conflict)
        elif strategy == ConflictStrategy.MERGE:
            resolved = self._resolve_merge(conflict)
        elif strategy == ConflictStrategy.CUSTOM and self._custom_resolver:
            resolved = self._custom_resolver(conflict)
        else:
            _LOGGER.warning("Unknown or unconfigured strategy %s for %s", strategy, key)
            return None
        
        if resolved:
            conflict.resolution = strategy.value
            conflict.resolved_state = resolved
            self._state_store[key] = resolved
            del self._conflicts[key]
            _LOGGER.info("Conflict resolved for %s: version=%d", key, resolved.version)
        
        return resolved
    
    def _resolve_last_write_wins(self, conflict: StateConflict) -> VersionedState:
        """Resolve by taking the most recently updated state."""
        if conflict.local_state.updated_at >= conflict.remote_state.updated_at:
            winner = conflict.local_state
        else:
            winner = conflict.remote_state
        
        # Create merged vector clock
        merged_clock = winner.vector_clock.copy()
        merged_clock.merge(conflict.local_state.vector_clock)
        merged_clock.merge(conflict.remote_state.vector_clock)
        
        return VersionedState(
            key=winner.key,
            data=dict(winner.data),
            version=max(winner.version, conflict.local_state.version, conflict.remote_state.version) + 1,
            vector_clock=merged_clock,
            checksum=winner.checksum,
            updated_at=time.time(),
            node_id=self.node_id,
        )
    
    def _resolve_first_write_wins(self, conflict: StateConflict) -> VersionedState:
        """Resolve by taking the earliest updated state."""
        if conflict.local_state.updated_at <= conflict.remote_state.updated_at:
            winner = conflict.local_state
        else:
            winner = conflict.remote_state
        
        merged_clock = winner.vector_clock.copy()
        merged_clock.merge(conflict.local_state.vector_clock)
        merged_clock.merge(conflict.remote_state.vector_clock)
        
        return VersionedState(
            key=winner.key,
            data=dict(winner.data),
            version=max(winner.version, conflict.local_state.version, conflict.remote_state.version) + 1,
            vector_clock=merged_clock,
            checksum=winner.checksum,
            updated_at=time.time(),
            node_id=self.node_id,
        )
    
    def _resolve_merge(self, conflict: StateConflict) -> VersionedState:
        """Resolve by merging state data (deep merge)."""
        import copy
        
        # Deep merge: remote data as base, local data overrides
        merged_data = copy.deepcopy(conflict.remote_state.data)
        self._deep_merge(merged_data, conflict.local_state.data)
        
        merged_clock = conflict.local_state.vector_clock.copy()
        merged_clock.merge(conflict.remote_state.vector_clock)
        
        new_version = max(
            conflict.local_state.version,
            conflict.remote_state.version
        ) + 1
        
        resolved = VersionedState(
            key=conflict.local_state.key,
            data=merged_data,
            version=new_version,
            vector_clock=merged_clock,
            checksum="",
            updated_at=time.time(),
            node_id=self.node_id,
        )
        resolved.checksum = resolved.compute_checksum()
        
        return resolved
    
    def _deep_merge(self, base: Dict, override: Dict) -> None:
        """Deep merge override into base (modifies base in place)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def set_custom_resolver(self, resolver: callable) -> None:
        """Set a custom conflict resolver callback.
        
        Resolver signature: (StateConflict) -> Optional[VersionedState]
        """
        self._custom_resolver = resolver
        _LOGGER.info("Custom conflict resolver registered")
    
    # Partition reconciliation
    
    def start_partition(self, peers: List[str]) -> None:
        """Mark the start of a network partition."""
        self._partition_start = time.time()
        self._partition_peers = list(peers)
        _LOGGER.info("Network partition started with peers: %s", peers)
    
    def end_partition(
        self,
        peer_states: Dict[str, Dict[str, VersionedState]],
    ) -> ReconciliationResult:
        """End partition and reconcile states with peers.
        
        Args:
            peer_states: Dict of node_id -> {key -> VersionedState}
        
        Returns:
            Reconciliation result
        """
        if self._partition_start is None:
            _LOGGER.warning("end_partition called without start_partition")
            self._partition_start = time.time()
        
        partition_duration = (time.time() - self._partition_start) * 1000
        self._partition_start = None
        
        conflicts_resolved = 0
        conflicts_unresolved = 0
        all_states: Dict[str, List[VersionedState]] = {}
        
        # Collect all states for each key from all nodes
        all_states = self._collect_all_states(peer_states)
        
        # Reconcile each key
        reconciled = []
        for key, versions in all_states.items():
            if len(versions) == 1:
                # No conflict, just adopt the single version
                reconciled.append(versions[0])
            else:
                # Multiple versions - need to resolve
                resolved = self._reconcile_key(key, versions)
                if resolved:
                    reconciled.append(resolved)
                    conflicts_resolved += 1
                else:
                    conflicts_unresolved += 1
        
        self._partition_peers = []
        
        result = ReconciliationResult(
            reconciled_states=reconciled,
            conflicts_resolved=conflicts_resolved,
            conflicts_unresolved=conflicts_unresolved,
            partition_duration_ms=partition_duration,
            nodes_synced=list(peer_states.keys()) + [self.node_id],
        )
        
        _LOGGER.info(
            "Partition reconciliation complete: %d resolved, %d unresolved, %.0fms duration",
            conflicts_resolved, conflicts_unresolved, partition_duration
        )
        
        return result
    
    def _collect_all_states(
        self,
        peer_states: Dict[str, Dict[str, VersionedState]],
    ) -> Dict[str, List[VersionedState]]:
        """Collect all versions of each state from all nodes."""
        all_states: Dict[str, List[VersionedState]] = {}
        
        # Add local states
        for key, state in self._state_store.items():
            all_states.setdefault(key, []).append(state)
        
        # Add peer states
        for node_id, states in peer_states.items():
            for key, state in states.items():
                all_states.setdefault(key, []).append(state)
        
        return all_states
    
    def _reconcile_key(
        self,
        key: str,
        versions: List[VersionedState],
    ) -> Optional[VersionedState]:
        """Reconcile multiple versions of a single key."""
        if not versions:
            return None
        
        # Find the version with the highest vector clock (most recent causally)
        best = versions[0]
        for v in versions[1:]:
            if v.vector_clock.happens_before(best.vector_clock):
                continue
            elif best.vector_clock.happens_before(v.vector_clock):
                best = v
            else:
                # Concurrent - use last-write-wins as tiebreaker
                if v.updated_at > best.updated_at:
                    best = v
        
        # Create reconciled state with merged clock
        merged_clock = VectorClock()
        for v in versions:
            merged_clock.merge(v.vector_clock)
        
        reconciled = VersionedState(
            key=key,
            data=dict(best.data),
            version=best.version + 1,
            vector_clock=merged_clock,
            checksum=best.checksum,
            updated_at=time.time(),
            node_id=self.node_id,
        )
        
        self._state_store[key] = reconciled
        return reconciled
    
    # Consistency verification
    
    def verify_consistency(
        self,
        peer_states: Dict[str, Dict[str, VersionedState]],
        level: Optional[ConsistencyLevel] = None,
    ) -> Dict[str, Any]:
        """Verify consistency across nodes.
        
        Args:
            peer_states: States from peer nodes
            level: Consistency level to verify (uses instance default if None)
        
        Returns:
            Verification report
        """
        level = level or self.consistency_level
        report = {
            "level": level.value,
            "consistent": True,
            "inconsistencies": [],
            "checked_at": time.time(),
            "node_count": len(peer_states) + 1,
        }
        
        all_keys = set(self._state_store.keys())
        for states in peer_states.values():
            all_keys.update(states.keys())
        
        for key in all_keys:
            local = self._state_store.get(key)
            peer_versions = []
            
            for node_id, states in peer_states.items():
                if key in states:
                    peer_versions.append((node_id, states[key]))
            
            inconsistency = self._check_key_consistency(key, local, peer_versions, level)
            if inconsistency:
                report["inconsistencies"].append(inconsistency)
                report["consistent"] = False
        
        return report
    
    def _check_key_consistency(
        self,
        key: str,
        local: Optional[VersionedState],
        peers: List[Tuple[str, VersionedState]],
        level: ConsistencyLevel,
    ) -> Optional[Dict[str, Any]]:
        """Check consistency for a single key."""
        if local is None and not peers:
            return None
        
        if level == ConsistencyLevel.LINEARIZABLE:
            # All nodes must have identical state
            if not peers:
                return None
            
            for node_id, peer_state in peers:
                if local is None:
                    return {
                        "key": key,
                        "type": "missing_local",
                        "description": f"Key missing on local node, present on {node_id}",
                    }
                if local.checksum != peer_state.checksum:
                    return {
                        "key": key,
                        "type": "checksum_mismatch",
                        "local_checksum": local.checksum,
                        "peer_checksum": peer_state.checksum,
                        "peer_node": node_id,
                    }
        
        elif level == ConsistencyLevel.SEQUENTIAL:
            # Versions must be causally ordered (no concurrent updates)
            all_states = [local] + [s for _, s in peers] if local else [s for _, s in peers]
            for i, s1 in enumerate(all_states):
                for s2 in all_states[i+1:]:
                    if s1.vector_clock.concurrent_with(s2.vector_clock):
                        return {
                            "key": key,
                            "type": "concurrent_updates",
                            "version_a": s1.version,
                            "version_b": s2.version,
                            "description": "Concurrent updates detected (violates sequential consistency)",
                        }
        
        # EVENTUAL: No immediate consistency required
        return None
    
    # Status and diagnostics
    
    def get_status(self) -> Dict[str, Any]:
        """Get current consistency manager status."""
        return {
            "node_id": self.node_id,
            "consistency_level": self.consistency_level.value,
            "default_strategy": self.default_strategy.value,
            "state_count": len(self._state_store),
            "pending_conflicts": len(self._conflicts),
            "in_partition": self._partition_start is not None,
            "partition_peers": self._partition_peers,
        }
    
    def get_conflicts(self) -> List[Dict[str, Any]]:
        """Get all pending conflicts."""
        return [c.to_dict() for c in self._conflicts.values()]
    
    def clear_state(self, key: Optional[str] = None) -> None:
        """Clear state(s)."""
        if key:
            self._state_store.pop(key, None)
            self._conflicts.pop(key, None)
        else:
            self._state_store.clear()
            self._conflicts.clear()
        _LOGGER.info("State cleared (%s)", key or "all")
