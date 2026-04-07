"""Entity-Relation-Entity (ERE) Query Patterns for Knowledge Graph.

Provides pattern matching for common graph traversal patterns used in
PilotSuite's smart home context:
- Entity → Entity relationships
- Entity → Area/Zone relationships
- Pattern → Entity triggers
- Mood-contextual queries
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import EdgeType, GraphResult, Node, NodeType

_LOGGER = logging.getLogger(__name__)


# ==================== Pattern Types ====================

@dataclass
class EntityRelationPattern:
    """Base class for entity-relation-entity patterns."""
    name: str
    description: str = ""


@dataclass
class DirectRelation(EntityRelationPattern):
    """A → B directly (one hop)."""
    source_type: NodeType
    source_id: str
    edge_type: EdgeType
    target_type: NodeType
    target_id: Optional[str] = None


@dataclass
class MultiHopRelation(EntityRelationPattern):
    """A → ... → B (multiple hops)."""
    source_type: NodeType
    source_id: str
    hops: list[tuple[EdgeType, NodeType]]
    min_hops: int = 1
    max_hops: int = 3


@dataclass
class PatternChain(EntityRelationPattern):
    """Pattern: if A then B (trigger chain)."""
    trigger_entity_id: str
    triggered_entity_id: str
    min_confidence: float = 0.5


@dataclass
class MoodContextualQuery(EntityRelationPattern):
    """Query entities/patterns by mood context."""
    mood: str
    time_context: Optional[str] = None
    zone_id: Optional[str] = None


@dataclass
class CapabilityQuery(EntityRelationPattern):
    """Query entities by capabilities."""
    capability: str
    zone_id: Optional[str] = None


# ==================== Query Executor ====================

class EntityRelationQueryExecutor:
    """
    Executes Entity-Relation-Entity patterns against the graph store.

    Example:
        executor = EntityRelationQueryExecutor(graph_store)
        result = executor.find_related_entities(
            entity_id="light.kitchen",
            edge_type=EdgeType.BELONGS_TO,
            max_results=20,
        )
    """

    def __init__(self, graph_store: Any) -> None:
        self._store = graph_store

    def find_related_entities(
        self,
        entity_id: str,
        edge_type: Optional[EdgeType] = None,
        direction: str = "out",  # "out", "in", "both"
        max_results: int = 50,
        min_confidence: float = 0.0,
    ) -> GraphResult:
        """
        Find entities directly related to the given entity.

        Args:
            entity_id: Source entity ID
            edge_type: Filter by edge type (None for all)
            direction: Traversal direction ("out", "in", "both")
            max_results: Maximum results to return
            min_confidence: Minimum confidence threshold

        Returns:
            GraphResult with matching nodes and edges
        """
        edges = self._store.get_edges_by_node(
            entity_id,
            edge_type=edge_type,
            direction=direction,
        )

        # Filter by confidence
        if min_confidence > 0:
            edges = [e for e in edges if e.confidence >= min_confidence]

        # Collect unique nodes
        node_ids = {entity_id}
        for edge in edges:
            node_ids.add(edge.source)
            node_ids.add(edge.target)

        nodes = []
        for nid in node_ids:
            node = self._store.get_node(nid)
            if node:
                nodes.append(node)

        # Limit results
        edges = edges[:max_results]
        if len(nodes) > max_results:
            nodes = nodes[:max_results]

        return GraphResult(
            nodes=nodes,
            edges=edges,
            confidence=sum(e.confidence for e in edges) / len(edges) if edges else 0.0,
            sources=["entity_relation_query"],
        )

    def find_entities_by_pattern(
        self,
        pattern_id: str,
        max_hops: int = 2,
    ) -> GraphResult:
        """
        Find all entities triggered by a habitus pattern.

        Args:
            pattern_id: The pattern node ID
            max_hops: Maximum traversal depth

        Returns:
            GraphResult with triggered entities
        """
        # Get the pattern node
        pattern_node = self._store.get_node(pattern_id)
        if not pattern_node or pattern_node.type != NodeType.PATTERN:
            return GraphResult(nodes=[], edges=[])

        # Find TRIGGERS edges from this pattern
        trigger_edges = self._store.get_edges_by_node(
            pattern_id,
            edge_type=EdgeType.TRIGGERS,
            direction="out",
        )

        # Collect triggered entity nodes
        nodes = [pattern_node]
        target_ids = {e.target for e in trigger_edges}

        for tid in target_ids:
            node = self._store.get_node(tid)
            if node:
                nodes.append(node)

        return GraphResult(
            nodes=nodes,
            edges=trigger_edges,
            confidence=sum(e.confidence for e in trigger_edges) / len(trigger_edges) if trigger_edges else 0.0,
            sources=["pattern_chain_query"],
        )

    def find_entities_by_capability(
        self,
        capability: str,
        zone_id: Optional[str] = None,
    ) -> GraphResult:
        """
        Find all entities with a specific capability.

        Args:
            capability: Capability name (e.g., "dimmable", "color_temp")
            zone_id: Optional zone filter

        Returns:
            GraphResult with matching entities
        """
        # Find capability nodes
        cap_nodes = self._store.get_nodes_by_type(NodeType.CAPABILITY, limit=100)
        cap_node_ids = {n.id for n in cap_nodes if capability.lower() in n.id.lower()}

        # Find entities with these capabilities
        entity_nodes = []
        entity_edges = []

        for cap_id in cap_node_ids:
            cap_edges = self._store.get_edges_by_node(
                cap_id,
                edge_type=EdgeType.HAS_CAPABILITY,
                direction="in",
            )
            for edge in cap_edges:
                node = self._store.get_node(edge.source)
                if node:
                    # Apply zone filter if specified
                    if zone_id:
                        zone_edges = self._store.get_edges_by_node(
                            node.id,
                            edge_type=EdgeType.BELONGS_TO,
                            direction="out",
                        )
                        zone_ids = {e.target for e in zone_edges if e.target.startswith(zone_id)}
                        if not zone_ids:
                            continue

                    entity_nodes.append(node)
                    entity_edges.append(edge)

        return GraphResult(
            nodes=entity_nodes,
            edges=entity_edges,
            confidence=1.0,
            sources=["capability_query"],
        )

    def find_zone_entities(
        self,
        zone_id: str,
        domain: Optional[str] = None,
        include_areas: bool = True,
    ) -> GraphResult:
        """
        Find all entities belonging to a zone.

        Args:
            zone_id: Zone identifier
            domain: Optional domain filter (e.g., "light", "sensor")
            include_areas: Whether to include entities from child areas

        Returns:
            GraphResult with zone entities
        """
        zone_node = self._store.get_node(zone_id)
        if not zone_node:
            return GraphResult(nodes=[], edges=[])

        # Direct BELONGS_TO edges to zone
        direct_edges = self._store.get_edges_by_node(
            zone_id,
            edge_type=EdgeType.BELONGS_TO,
            direction="in",
        )

        nodes = [zone_node]
        edges = []
        area_ids = set()

        for edge in direct_edges:
            node = self._store.get_node(edge.source)
            if node:
                if node.type == NodeType.AREA:
                    area_ids.add(node.id)
                elif domain is None or _node_domain(node) == domain:
                    nodes.append(node)
                    edges.append(edge)

        # Optionally include area children
        if include_areas and area_ids:
            for area_id in area_ids:
                area_edges = self._store.get_edges_by_node(
                    area_id,
                    edge_type=EdgeType.BELONGS_TO,
                    direction="in",
                )
                for edge in area_edges:
                    node = self._store.get_node(edge.source)
                    if node and (domain is None or _node_domain(node) == domain):
                        nodes.append(node)
                        edges.append(edge)

        return GraphResult(
            nodes=nodes,
            edges=edges,
            confidence=1.0,
            sources=["zone_entity_query"],
        )

    def find_contextual_entities(
        self,
        mood: str,
        time_context: Optional[str] = None,
        zone_id: Optional[str] = None,
    ) -> GraphResult:
        """
        Find entities/patterns relevant to a mood and optional time context.

        Args:
            mood: Mood identifier (e.g., "relax", "focus", "active")
            time_context: Optional time context (e.g., "morning", "evening")
            zone_id: Optional zone filter

        Returns:
            GraphResult with mood-contextual entities
        """
        # Get mood node
        mood_nodes = self._store.get_nodes_by_type(NodeType.MOOD, limit=50)
        mood_node = next((n for n in mood_nodes if n.id == mood or n.label == mood), None)

        if not mood_node:
            return GraphResult(nodes=[], edges=[])

        # Find RELATES_TO_MOOD edges
        mood_edges = self._store.get_edges_by_node(
            mood_node.id,
            edge_type=EdgeType.RELATES_TO_MOOD,
            direction="in",
        )

        nodes = [mood_node]
        edges = []

        for edge in mood_edges:
            # Filter by zone if specified
            if zone_id:
                zone_edges = self._store.get_edges_by_node(
                    edge.source,
                    edge_type=EdgeType.BELONGS_TO,
                    direction="out",
                )
                zone_ids = {e.target for e in zone_edges}
                if not any(zid.startswith(zone_id) for zid in zone_ids):
                    continue

            node = self._store.get_node(edge.source)
            if node:
                nodes.append(node)
                edges.append(edge)

        # Filter by time context if specified
        if time_context:
            time_nodes = self._store.get_nodes_by_type(NodeType.TIME_CONTEXT, limit=50)
            time_node = next((n for n in time_nodes if n.label == time_context), None)

            if time_node:
                time_filtered = []
                for node, edge in zip(nodes, edges):
                    # Check if entity is ACTIVE_DURING this time
                    active_edges = self._store.get_edges_by_node(
                        node.id if hasattr(node, 'id') else edge.source,
                        edge_type=EdgeType.ACTIVE_DURING,
                        direction="out",
                    )
                    if any(e.target == time_node.id for e in active_edges):
                        time_filtered.append((node, edge))

                nodes, edges = zip(*time_filtered) if time_filtered else ([mood_node], [])

        return GraphResult(
            nodes=list(nodes),
            edges=list(edges),
            confidence=sum(e.confidence for e in edges) / len(edges) if edges else 0.0,
            sources=["mood_contextual_query"],
        )


def _node_domain(node: Node) -> Optional[str]:
    """Extract domain from entity node ID."""
    if node.type == NodeType.ENTITY and "." in node.id:
        return node.id.split(".")[0]
    return None
