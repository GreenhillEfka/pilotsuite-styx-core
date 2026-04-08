"""
Brain Graph service providing high-level graph operations.
"""

import json
import logging
import queue
import threading
import time
from typing import Dict, List, Optional, Any, Tuple, Iterable

from .model import GraphNode, GraphEdge, NodeKind, EdgeType
from .store import BrainGraphStore
from ..performance import brain_graph_cache

logger = logging.getLogger(__name__)

# Alias for backwards compatibility
GraphStore = BrainGraphStore


def _invalidate_graph_cache():
    """Invalidate all graph state cache entries."""
    brain_graph_cache.clear()


class BrainGraphService:
    """High-level service for brain graph operations."""
    
    def __init__(
        self,
        store: Optional[GraphStore] = None,
        node_half_life_hours: float = 24.0,
        edge_half_life_hours: float = 12.0,
        prune_interval_minutes: int = 60,
    ):
        self.store = store or GraphStore()
        self.node_half_life_hours = node_half_life_hours
        self.edge_half_life_hours = edge_half_life_hours

        # Batch processing support for performance
        self._batch_mode = False
        self._batch_size = 0
        self._pending_invalidations = 0

        # Pruning counter for deterministic cleanup
        self._operation_count = 0
        self._prune_interval = 100  # Prune every N operations

        # Thread-safety: protects _batch_mode, _pending_invalidations, _operation_count
        self._lock = threading.Lock()

        # SSE event broadcasting (v5.0.0)
        self._sse_subscribers: List[queue.Queue] = []
        self._sse_lock = threading.Lock()

        # Scheduled pruning: daemon thread that runs prune_graph at fixed intervals
        self._prune_interval_seconds = max(60, prune_interval_minutes * 60)
        self._prune_stop = threading.Event()
        self._prune_thread: Optional[threading.Thread] = None
        self._last_prune_stats: Optional[Dict[str, Any]] = None

    # --- Scheduled Pruning -------------------------------------------------

    def start_scheduled_pruning(self) -> None:
        """Start background daemon thread for periodic graph pruning."""
        if self._prune_thread is not None and self._prune_thread.is_alive():
            return
        self._prune_stop.clear()
        self._prune_thread = threading.Thread(
            target=self._prune_loop,
            name="brain-graph-pruner",
            daemon=True,
        )
        self._prune_thread.start()
        logger.info(
            "Brain graph scheduled pruning started (every %d min)",
            self._prune_interval_seconds // 60,
        )

    def stop_scheduled_pruning(self) -> None:
        """Signal the pruning thread to stop."""
        self._prune_stop.set()
        if self._prune_thread is not None:
            self._prune_thread.join(timeout=5)
            self._prune_thread = None

    # --- SSE Event Broadcasting (v5.0.0) ------------------------------------

    def subscribe_sse(self) -> queue.Queue:
        """Create a new SSE subscriber queue.

        Returns a Queue that receives event dicts:
            {"event": "node_updated"|"edge_updated"|"graph_pruned",
             "data": {...}, "timestamp_ms": int}

        Caller MUST call unsubscribe_sse() when done.
        """
        q: queue.Queue = queue.Queue(maxsize=256)
        with self._sse_lock:
            self._sse_subscribers.append(q)
        logger.debug("SSE subscriber added (total: %d)", len(self._sse_subscribers))
        return q

    def unsubscribe_sse(self, q: queue.Queue) -> None:
        """Remove an SSE subscriber queue."""
        with self._sse_lock:
            try:
                self._sse_subscribers.remove(q)
            except ValueError:
                pass
        logger.debug("SSE subscriber removed (total: %d)", len(self._sse_subscribers))

    def _broadcast_sse(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast an event to all SSE subscribers (non-blocking)."""
        msg = {
            "event": event_type,
            "data": data,
            "timestamp_ms": int(time.time() * 1000),
        }
        dead: List[queue.Queue] = []
        with self._sse_lock:
            for q in self._sse_subscribers:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                try:
                    self._sse_subscribers.remove(q)
                except ValueError:
                    pass

    def _prune_loop(self) -> None:
        """Background loop: sleep then prune, repeat until stopped."""
        while not self._prune_stop.wait(timeout=self._prune_interval_seconds):
            try:
                stats = self.store.prune_graph()
                self._last_prune_stats = {
                    **stats,
                    "pruned_at": time.time(),
                    "scheduled": True,
                }
                removed = stats.get("nodes_removed", 0) + stats.get("edges_removed", 0)
                if removed > 0:
                    _invalidate_graph_cache()
                    self._broadcast_sse("graph_pruned", stats)
                    logger.info("Scheduled prune: removed %d nodes, %d edges",
                                stats.get("nodes_removed", 0), stats.get("edges_removed", 0))
                else:
                    logger.debug("Scheduled prune: nothing to remove")
            except Exception:
                logger.exception("Scheduled prune failed")
    
    def begin_batch(self, size: int = 50):
        """Start batch processing mode - delays cache invalidation until commit."""
        with self._lock:
            self._batch_mode = True
            self._batch_size = size
            self._pending_invalidations = 0

    def commit_batch(self):
        """Commit batch and invalidate cache once if needed."""
        with self._lock:
            should_invalidate = self._batch_mode and self._pending_invalidations > 0
            self._batch_mode = False
            self._pending_invalidations = 0
        if should_invalidate:
            _invalidate_graph_cache()

    def rollback_batch(self):
        """Rollback batch without invalidating cache."""
        with self._lock:
            self._batch_mode = False
            self._pending_invalidations = 0
    
    def touch_node(
        self,
        node_id: str,
        delta: float = 1.0,
        label: Optional[str] = None,
        kind: Optional[NodeKind] = None,
        domain: Optional[str] = None,
        meta_patch: Optional[Dict[str, Any]] = None,
        source: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None
    ) -> GraphNode:
        """Touch a node, updating its score and metadata."""
        now_ms = int(time.time() * 1000)
        
        # Get existing node or create new one
        existing_node = self.store.get_node(node_id)
        
        if existing_node:
            # Update existing node
            new_score = max(0.0, existing_node.effective_score(now_ms, self.node_half_life_hours) + delta)
            new_label = label or existing_node.label
            new_kind = kind or existing_node.kind
            new_domain = domain or existing_node.domain
            new_source = source or existing_node.source
            new_tags = tags or existing_node.tags
            
            # Merge meta
            new_meta = existing_node.meta.copy() if existing_node.meta else {}
            if meta_patch:
                new_meta.update(meta_patch)
        else:
            # Create new node  
            if not label or not kind:
                raise ValueError("label and kind are required for new nodes")
                
            new_score = max(0.0, delta)
            new_label = label
            new_kind = kind
            new_domain = domain
            new_source = source
            new_tags = tags
            new_meta = meta_patch or {}
        
        # Create updated node
        updated_node = GraphNode(
            id=node_id,
            kind=new_kind,
            label=new_label,
            updated_at_ms=now_ms,
            score=new_score,
            domain=new_domain,
            source=new_source,
            tags=new_tags,
            meta=new_meta,
        )
        
        # Store the node
        self.store.upsert_node(updated_node)
        
        # Invalidate graph cache on updates (batched) + trigger pruning
        should_invalidate = False
        should_prune = False
        with self._lock:
            if self._batch_mode:
                self._pending_invalidations += 1
            else:
                should_invalidate = True
            self._operation_count += 1
            if self._operation_count >= self._prune_interval:
                self._operation_count = 0
                should_prune = True

        if should_invalidate:
            _invalidate_graph_cache()
        if should_prune:
            self.store.prune_graph(now_ms)

        # Broadcast SSE event (v5.0.0)
        self._broadcast_sse("node_updated", {
            "id": updated_node.id,
            "kind": updated_node.kind,
            "label": updated_node.label,
            "score": updated_node.score,
        })

        return updated_node
    
    def touch_edge(
        self,
        from_node: str,
        edge_type: EdgeType,
        to_node: str,
        delta: float = 1.0,
        meta_patch: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, str]] = None
    ) -> GraphEdge:
        """Touch an edge, updating its weight and metadata."""
        now_ms = int(time.time() * 1000)
        
        edge_id = GraphEdge.create_id(from_node, edge_type, to_node)
        
        # Get existing edge or create new one
        existing_edges = self.store.get_edges(from_node=from_node, to_node=to_node, edge_types=[edge_type])
        existing_edge = next((e for e in existing_edges if e.id == edge_id), None)
        
        if existing_edge:
            # Update existing edge
            new_weight = max(0.0, existing_edge.effective_weight(now_ms, self.edge_half_life_hours) + delta)
            new_evidence = evidence or existing_edge.evidence
            
            # Merge meta
            new_meta = existing_edge.meta.copy() if existing_edge.meta else {}
            if meta_patch:
                new_meta.update(meta_patch)
        else:
            # Create new edge
            new_weight = max(0.0, delta)
            new_evidence = evidence
            new_meta = meta_patch or {}
        
        # Create updated edge
        updated_edge = GraphEdge(
            id=edge_id,
            from_node=from_node,
            to_node=to_node,
            edge_type=edge_type,
            updated_at_ms=now_ms,
            weight=new_weight,
            evidence=new_evidence,
            meta=new_meta,
        )
        
        # Store the edge
        self.store.upsert_edge(updated_edge)
        
        # Invalidate graph cache on edge updates (batched)
        should_invalidate = False
        with self._lock:
            if self._batch_mode:
                self._pending_invalidations += 1
            else:
                should_invalidate = True
        if should_invalidate:
            _invalidate_graph_cache()

        # Broadcast SSE event (v5.0.0)
        self._broadcast_sse("edge_updated", {
            "id": updated_edge.id,
            "from": updated_edge.from_node,
            "to": updated_edge.to_node,
            "type": updated_edge.edge_type,
            "weight": updated_edge.weight,
        })

        return updated_edge
    
    def link(
        self,
        from_node: str,
        edge_type: EdgeType, 
        to_node: str,
        initial_weight: float = 1.0,
        evidence: Optional[Dict[str, str]] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> GraphEdge:
        """Create or strengthen a link between nodes."""
        return self.touch_edge(
            from_node=from_node,
            edge_type=edge_type,
            to_node=to_node,
            delta=initial_weight,
            evidence=evidence,
            meta_patch=meta
        )
    
    def get_graph_state(
        self,
        kinds: Optional[List[NodeKind]] = None,
        domains: Optional[List[str]] = None,
        center_node: Optional[str] = None,
        hops: int = 1,
        limit_nodes: Optional[int] = None,
        limit_edges: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get current graph state with optional filtering."""
        now_ms = int(time.time() * 1000)
        
        if center_node:
            # Get neighborhood
            nodes, edges = self.store.get_neighborhood(
                center_node=center_node,
                hops=hops,
                max_nodes=limit_nodes,
                max_edges=limit_edges
            )
        else:
            # Get filtered nodes
            nodes = self.store.get_nodes(
                kinds=kinds,
                domains=domains,
                limit=limit_nodes
            )
            
            # Get edges between these nodes
            node_ids = {node.id for node in nodes}
            all_edges = []
            
            for node in nodes:
                node_edges = self.store.get_edges(from_node=node.id)
                for edge in node_edges:
                    if edge.to_node in node_ids and edge not in all_edges:
                        all_edges.append(edge)
            
            # Apply edge limit
            if limit_edges and len(all_edges) > limit_edges:
                all_edges = sorted(all_edges, key=lambda e: e.effective_weight(now_ms), reverse=True)[:limit_edges]
                
            edges = all_edges
        
        # Convert to serializable format
        return {
            "version": 1,
            "generated_at_ms": now_ms,
            "limits": {
                "nodes_max": self.store.max_nodes,
                "edges_max": self.store.max_edges,
            },
            "nodes": [
                {
                    "id": node.id,
                    "kind": node.kind,
                    "label": node.label,
                    "domain": node.domain,
                    "score": node.effective_score(now_ms, self.node_half_life_hours),
                    "updated_at_ms": node.updated_at_ms,
                    "source": node.source,
                    "tags": node.tags,
                    "meta": node.meta,
                }
                for node in nodes
            ],
            "edges": [
                {
                    "id": edge.id,
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "type": edge.edge_type,
                    "weight": edge.effective_weight(now_ms, self.edge_half_life_hours),
                    "updated_at_ms": edge.updated_at_ms,
                    "evidence": edge.evidence,
                    "meta": edge.meta,
                }
                for edge in edges
            ]
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current graph statistics."""
        store_stats = self.store.get_stats()

        result = {
            **store_stats,
            "config": {
                "node_half_life_hours": self.node_half_life_hours,
                "edge_half_life_hours": self.edge_half_life_hours,
                "node_min_score": self.store.node_min_score,
                "edge_min_weight": self.store.edge_min_weight,
                "prune_interval_minutes": self._prune_interval_seconds // 60,
            },
        }
        if self._last_prune_stats is not None:
            result["last_prune"] = self._last_prune_stats
        return result
    
    def export_state(
        self,
        kind: Iterable[str] | None = None,
        domain: Iterable[str] | None = None,
        center: str | None = None,
        hops: int = 1,
        limit_nodes: int = 500,
        limit_edges: int = 1500,
        now: int | None = None,
    ) -> dict[str, Any]:
        """Alias for get_graph_state with different parameter names."""
        return self.get_graph_state(
            kinds=list(kind) if kind else None,
            domains=list(domain) if domain else None,
            center_node=center,
            hops=hops,
            limit_nodes=limit_nodes,
            limit_edges=limit_edges,
        )
    
    def prune_now(self) -> Dict[str, int]:
        """Manually trigger graph pruning."""
        return self.store.prune_graph()
    
    def prune(self) -> Dict[str, int]:
        """Alias for prune_now for backward compatibility."""
        return self.prune_now()
    
    def process_ha_event(self, event_data: Dict[str, Any]):
        """Process a Home Assistant event and update the graph."""
        event_type = event_data.get("event_type", "")
        
        if event_type == "state_changed":
            self._process_state_change(event_data)
        elif event_type == "call_service":
            self._process_service_call(event_data)
        
        # Trigger inference: look for causal relationships between recent events
        self._infer_triggers(event_data)
    
    def _infer_triggers(self, event_data: Dict[str, Any]):
        """Infer causal relationships between events based on timing."""
        event_type = event_data.get("event_type", "")
        timestamp_ms = int(time.time() * 1000)
        
        if event_type != "state_changed":
            return  # Only infer triggers for state changes
            
        entity_id = event_data.get("data", {}).get("entity_id", "")
        context_id = event_data.get("context", {}).get("id", "")
        parent_id = event_data.get("context", {}).get("parent_id", "")
        
        if not entity_id:
            return
            
        # Look for service calls in the last 10 seconds that might have caused this
        # This would ideally query recent events, but for now we'll use a simple heuristic
        # based on the context parent_id (HA provides this for triggered events)
        
        if parent_id:
            # This state change was likely triggered by a service call
            trigger_node_id = f"ha.trigger:{parent_id[:8]}"  # Shortened for privacy
            
            self.touch_node(
                node_id=trigger_node_id,
                kind="event",
                label=f"Trigger {parent_id[:8]}",
                source={"system": "ha", "name": "context_inference"},
                tags=["trigger", "causal"]
            )
            
            # Link trigger to affected entity
            self.link(
                from_node=trigger_node_id,
                edge_type="triggered_by",
                to_node=f"ha.entity:{entity_id}",
                evidence={"kind": "context_parent", "ref": parent_id[:8]}
            )
    
    def infer_patterns(self) -> Dict[str, Any]:
        """Infer common patterns from the current graph state."""
        now_ms = int(time.time() * 1000)
        
        # Get all nodes and edges
        all_nodes = self.store.get_nodes(limit=None)
        all_edges = self.store.get_edges()
        
        patterns = {
            "frequently_controlled_entities": [],
            "zone_activity_hubs": [],
            "service_usage_patterns": [],
            "trigger_chains": []
        }
        
        # Pattern 1: Most controlled entities (high service call correlation)
        entity_control_scores = {}
        for edge in all_edges:
            if (edge.edge_type == "affects" and 
                edge.from_node.startswith("ha.service:") and 
                edge.to_node.startswith("ha.entity:")):
                
                entity_id = edge.to_node
                score = edge.effective_weight(now_ms, self.edge_half_life_hours)
                entity_control_scores[entity_id] = entity_control_scores.get(entity_id, 0) + score
        
        top_controlled = sorted(entity_control_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        patterns["frequently_controlled_entities"] = [
            {"entity_id": entity_id.replace("ha.entity:", ""), "control_score": score}
            for entity_id, score in top_controlled
        ]
        
        # Pattern 2: Zone activity (entities + triggers in zones)
        zone_activity = {}
        for edge in all_edges:
            if edge.edge_type == "in_zone" and edge.to_node.startswith("zone:"):
                zone_id = edge.to_node
                weight = edge.effective_weight(now_ms, self.edge_half_life_hours)
                zone_activity[zone_id] = zone_activity.get(zone_id, 0) + weight
        
        top_zones = sorted(zone_activity.items(), key=lambda x: x[1], reverse=True)[:3]
        patterns["zone_activity_hubs"] = [
            {"zone_id": zone_id.replace("zone:", ""), "activity_score": score}
            for zone_id, score in top_zones
        ]
        
        return patterns
    
    def get_zone_entities(self, zone_id: str) -> Dict[str, Any]:
        """
        Get all entities in a specific zone.
        
        Args:
            zone_id: Zone identifier (e.g., "zone:kitchen" or "kitchen")
            
        Returns:
            Dict with entities, edges, and zone info
        """
        now_ms = int(time.time() * 1000)
        
        # Normalize zone_id
        if not zone_id.startswith("zone:"):
            zone_id = f"zone:{zone_id}"
        
        # Get zone node
        zone_node = self.store.get_node(zone_id)
        if not zone_node:
            return {"error": f"Zone not found: {zone_id}"}
        
        # Get all edges from/to zone
        zone_edges = self.store.get_edges(to_node=zone_id, edge_types=["in_zone"])
        entity_node_ids = set()
        
        for edge in zone_edges:
            if edge.from_node.startswith("ha.entity:"):
                entity_node_ids.add(edge.from_node)
        
        # Get entity nodes
        entities = []
        for node_id in entity_node_ids:
            node = self.store.get_node(node_id)
            if node:
                entities.append({
                    "id": node.id,
                    "label": node.label,
                    "kind": node.kind,
                    "domain": node.domain,
                    "score": node.effective_score(now_ms, self.node_half_life_hours),
                    "updated_at_ms": node.updated_at_ms
                })
        
        # Sort by score
        entities.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "zone": {
                "id": zone_node.id,
                "label": zone_node.label,
                "score": zone_node.effective_score(now_ms, self.node_half_life_hours)
            },
            "entities": entities,
            "entity_count": len(entities),
            "edges": [
                {"from": e.from_node, "to": e.to_node, "weight": e.effective_weight(now_ms)}
                for e in zone_edges
            ]
        }
    
    def get_zones(self) -> List[Dict[str, Any]]:
        """
        Get all zones from the brain graph.
        
        Returns:
            List of zone dictionaries with metadata
        """
        now_ms = int(time.time() * 1000)
        
        all_nodes = self.store.get_nodes(kinds=["zone"])
        zones = []
        
        for node in all_nodes:
            # Get entity count for this zone
            zone_edges = self.store.get_edges(to_node=node.id, edge_types=["in_zone"])
            entity_count = len([
                e for e in zone_edges 
                if e.from_node.startswith("ha.entity:")
            ])
            
            zones.append({
                "id": node.id,
                "label": node.label,
                "score": node.effective_score(now_ms, self.node_half_life_hours),
                "entity_count": entity_count,
                "updated_at_ms": node.updated_at_ms
            })
        
        # Sort by score (activity level)
        zones.sort(key=lambda x: x["score"], reverse=True)
        
        return zones
    
    def _process_state_change(self, event_data: Dict[str, Any]):
        """Process a state change event with enhanced zone inference."""
        # Extract entity info
        entity_id = event_data.get("data", {}).get("entity_id", "")
        if not entity_id:
            return
            
        new_state = event_data.get("data", {}).get("new_state", {})
        state_value = new_state.get("state", "")
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
        
        # Create/update entity node with higher salience for interactive entities
        salience_boost = 1.5 if domain in ['light', 'switch', 'cover', 'media_player'] else 1.0
        
        entity_node = self.touch_node(
            node_id=f"ha.entity:{entity_id}",
            kind="entity",
            label=entity_id.split(".")[-1].replace("_", " ").title(),
            domain=domain,
            source={"system": "ha", "name": "state_changed"},
            delta=salience_boost
        )
        
        # Enhanced zone inference from state values and attributes
        self._infer_and_link_zones(entity_id, state_value, new_state.get("attributes", {}))
        
        # Link to device if device_id is available
        device_id = new_state.get("attributes", {}).get("device_id")
        if device_id:
            device_node = self.touch_node(
                node_id=f"ha.device:{device_id}",
                kind="device",
                label=f"Device {device_id[:8]}",
                source={"system": "ha", "name": "device_registry"}
            )
            
            self.link(
                from_node=f"ha.entity:{entity_id}",
                edge_type="controls",
                to_node=f"ha.device:{device_id}",
                evidence={"kind": "device_registry", "ref": entity_id}
            )
    
    def _infer_and_link_zones(self, entity_id: str, state_value: str, attributes: Dict[str, Any]):
        """Infer zone relationships from entity state and attributes."""
        domain = entity_id.split(".")[0]
        entity_node_id = f"ha.entity:{entity_id}"
        
        # Method 1: Direct zone from state (person, device_tracker)
        if domain in ['person', 'device_tracker'] and state_value:
            if state_value not in ['unknown', 'unavailable', '']:
                zone_id = f"zone:{state_value}"
                zone_label = state_value.replace("_", " ").title()
                
                # Create/update zone node
                self.touch_node(
                    node_id=zone_id,
                    kind="zone", 
                    label=zone_label,
                    source={"system": "ha", "name": "zone_inference"}
                )
                
                # Link entity to zone
                self.link(
                    from_node=entity_node_id,
                    edge_type="in_zone",
                    to_node=zone_id,
                    evidence={"kind": "state_inference", "ref": f"state={state_value}"}
                )
        
        # Method 2: Area from friendly_name patterns
        friendly_name = attributes.get("friendly_name", "")
        if friendly_name:
            # Extract potential area/room from friendly name
            # Common patterns: "Kitchen Light", "Living Room TV", "Bedroom Fan"
            words = friendly_name.lower().split()
            potential_zones = []
            
            # Look for common room/area words
            room_indicators = [
                'kitchen', 'bedroom', 'bathroom', 'living', 'dining', 'office',
                'garage', 'basement', 'attic', 'hallway', 'entryway', 'patio',
                'balcony', 'study', 'guest', 'master', 'kids', 'family'
            ]
            
            for word in words:
                if word in room_indicators:
                    potential_zones.append(word)
            
            # Create zone links for detected areas
            for zone_name in potential_zones:
                zone_id = f"zone:{zone_name}"
                zone_label = zone_name.title()
                
                self.touch_node(
                    node_id=zone_id,
                    kind="zone",
                    label=zone_label,
                    source={"system": "ha", "name": "friendly_name_inference"}
                )
                
                self.link(
                    from_node=entity_node_id,
                    edge_type="in_zone", 
                    to_node=zone_id,
                    initial_weight=0.7,  # Lower confidence than direct state
                    evidence={"kind": "name_inference", "ref": f"friendly_name={friendly_name}"}
                )
        
        # Method 3: Entity ID patterns (e.g., "light.kitchen_main")
        entity_name = entity_id.split(".")[-1] if "." in entity_id else entity_id
        name_parts = entity_name.replace("_", " ").split()
        
        for part in name_parts:
            if part.lower() in ['kitchen', 'bedroom', 'bathroom', 'living', 'dining', 'office', 'garage']:
                zone_id = f"zone:{part.lower()}"
                zone_label = part.title()
                
                self.touch_node(
                    node_id=zone_id,
                    kind="zone",
                    label=zone_label,
                    source={"system": "ha", "name": "entity_name_inference"}
                )
                
                self.link(
                    from_node=entity_node_id,
                    edge_type="in_zone",
                    to_node=zone_id,
                    initial_weight=0.5,  # Lowest confidence
                    evidence={"kind": "entity_name_inference", "ref": f"entity_id={entity_id}"}
                )
        
    def _process_service_call(self, event_data: Dict[str, Any]):
        """Process a service call event with enhanced intentional action tracking."""
        service_data = event_data.get("data", {})
        domain = service_data.get("domain", "")
        service = service_data.get("service", "")
        
        if not domain or not service:
            return
            
        # Create/update service node with high salience (intentional actions matter more)
        service_id = f"{domain}.{service}"
        service_node = self.touch_node(
            node_id=f"ha.service:{service_id}",
            kind="concept", 
            label=f"{domain.title()} {service.replace('_', ' ').title()}",
            source={"system": "ha", "name": "call_service"},
            delta=2.0,  # Higher salience for intentional actions
            tags=["service_call", domain]
        )
        
        # Extract and link target entities
        call_data = service_data.get("service_data", {})
        target_entities = self._extract_target_entities(call_data)
        
        # Create stronger links to affected entities (intentional correlation)
        for entity_id in target_entities:
            # Boost entity salience when explicitly controlled
            # Extract entity label from entity_id (e.g., "light.kitchen" -> "Kitchen")
            entity_label = entity_id.split(".", 1)[-1].replace("_", " ").title() if "." in entity_id else entity_id
            self.touch_node(
                node_id=f"ha.entity:{entity_id}",
                delta=1.2,  # Boost controlled entities
                label=entity_label,
                kind="entity",
                domain=entity_id.split(".", 1)[0] if "." in entity_id else "unknown",
                source={"system": "ha", "name": "service_target"}
            )
            
            # Create strong intentional edge
            self.link(
                from_node=f"ha.service:{service_id}",
                edge_type="affects",
                to_node=f"ha.entity:{entity_id}",
                initial_weight=1.5,  # Stronger than passive correlations
                evidence={"kind": "service_call", "ref": service_id, "summary": f"{service} → {entity_id}"}
            )
            
            # If entity has known zones, link service to zones too (spatial intent)
            entity_edges = self.store.get_edges(from_node=f"ha.entity:{entity_id}")
            for edge in entity_edges:
                if edge.edge_type == "in_zone" and edge.to_node.startswith("zone:"):
                    self.link(
                        from_node=f"ha.service:{service_id}",
                        edge_type="affects",
                        to_node=edge.to_node,
                        initial_weight=0.8,  # Lower than direct entity link
                        evidence={"kind": "spatial_inference", "ref": f"via {entity_id}"}
                    )
    
    def _extract_target_entities(self, service_data: Dict[str, Any]) -> List[str]:
        """Extract target entity IDs from service call data."""
        targets = []
        
        # Method 1: Direct entity_id parameter
        entity_id = service_data.get("entity_id")
        if entity_id:
            if isinstance(entity_id, str):
                targets.append(entity_id)
            elif isinstance(entity_id, list):
                targets.extend([e for e in entity_id if isinstance(e, str)])
        
        # Method 2: area_id (would target all entities in area)
        area_id = service_data.get("area_id")
        if area_id:
            # This would require HA area registry integration
            # For now, we'll create an area concept node
            area_node_id = f"ha.area:{area_id}"
            self.touch_node(
                node_id=area_node_id,
                kind="zone",
                label=f"Area {area_id}",
                source={"system": "ha", "name": "area_registry"}
            )
        
        # Method 3: device_id (would target entities of that device)
        device_id = service_data.get("device_id")
        if device_id:
            device_node_id = f"ha.device:{device_id}"
            self.touch_node(
                node_id=device_node_id,
                kind="device", 
                label=f"Device {device_id[:8]}",
                source={"system": "ha", "name": "device_registry"}
            )
        
        return targets