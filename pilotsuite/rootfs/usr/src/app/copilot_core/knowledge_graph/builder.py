"""Graph Builder for Knowledge Graph.

Builds the knowledge graph from Home Assistant states, entities, areas,
and tags. Creates nodes and edges based on HA state changes.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .models import Edge, EdgeType, Node, NodeType
from .graph_store import GraphStore, get_graph_store

_LOGGER = logging.getLogger(__name__)


class GraphBuilder:
    """Builds knowledge graph from Home Assistant data."""

    def __init__(self, store: Optional[GraphStore] = None) -> None:
        """Initialize the graph builder.
        
        Args:
            store: GraphStore instance (uses singleton if None)
        """
        self._store = store or get_graph_store()
        self._entity_cache: dict[str, Node] = {}
        self._area_cache: dict[str, Node] = {}
        self._domain_cache: dict[str, Node] = {}

    # ==================== Entity Management ====================

    def upsert_entity(
        self,
        entity_id: str,
        domain: str,
        label: Optional[str] = None,
        area_id: Optional[str] = None,
        capabilities: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        properties: Optional[dict[str, Any]] = None,
    ) -> Node:
        """Create or update an entity node.
        
        Args:
            entity_id: Home Assistant entity ID (e.g., "light.kitchen")
            domain: Entity domain (e.g., "light")
            label: Human-readable label
            area_id: Area/room ID this entity belongs to
            capabilities: List of capability names (e.g., ["dimmable", "color_temp"])
            tags: List of tag names (e.g., ["aicp.place.kueche"])
            properties: Additional properties
        
        Returns:
            The created/updated Node
        """
        now = int(time.time() * 1000)
        
        # Create domain node if needed
        domain_node = self._ensure_domain(domain)
        
        # Create entity node
        entity_node = Node(
            id=entity_id,
            type=NodeType.ENTITY,
            label=label or entity_id,
            properties=properties or {},
            updated_at=now,
        )
        self._store.add_node(entity_node)
        self._entity_cache[entity_id] = entity_node
        
        # Create BELONGS_TO edge to domain
        self._store.add_edge(Edge(
            source=entity_id,
            target=f"domain:{domain}",
            type=EdgeType.BELONGS_TO,
            weight=1.0,
            confidence=1.0,
            source_type="explicit",
        ))
        
        # Create area relationship if provided
        if area_id:
            area_node = self._ensure_area(area_id)
            self._store.add_edge(Edge(
                source=entity_id,
                target=area_id,
                type=EdgeType.BELONGS_TO,
                weight=1.0,
                confidence=1.0,
                source_type="explicit",
            ))
        
        # Create capability edges
        if capabilities:
            for cap in capabilities:
                self._ensure_capability(cap)
                self._store.add_edge(Edge(
                    source=entity_id,
                    target=f"cap:{cap}",
                    type=EdgeType.HAS_CAPABILITY,
                    weight=1.0,
                    confidence=1.0,
                    source_type="explicit",
                ))
        
        # Create tag edges
        if tags:
            for tag in tags:
                self._ensure_tag(tag)
                self._store.add_edge(Edge(
                    source=entity_id,
                    target=f"tag:{tag}",
                    type=EdgeType.HAS_TAG,
                    weight=1.0,
                    confidence=1.0,
                    source_type="explicit",
                ))
        
        _LOGGER.debug("Upserted entity %s with domain=%s, area=%s", entity_id, domain, area_id)
        return entity_node

    def _ensure_domain(self, domain: str) -> Node:
        """Ensure a domain node exists."""
        node_id = f"domain:{domain}"
        if node_id in self._domain_cache:
            return self._domain_cache[node_id]
        
        node = Node(
            id=node_id,
            type=NodeType.DOMAIN,
            label=domain,
            properties={"domain": domain},
        )
        self._store.add_node(node)
        self._domain_cache[node_id] = node
        return node

    def _ensure_area(self, area_id: str) -> Node:
        """Ensure an area node exists."""
        if area_id in self._area_cache:
            return self._area_cache[area_id]
        
        node = Node(
            id=area_id,
            type=NodeType.AREA,
            label=area_id,
            properties={},
        )
        self._store.add_node(node)
        self._area_cache[area_id] = node
        return node

    def _ensure_mood(self, mood: str) -> Node:
        """Ensure a mood node exists."""
        node_id = f"mood:{mood}"
        existing = self._store.get_node(node_id)
        if existing:
            return existing

        node = Node(
            id=node_id,
            type=NodeType.MOOD,
            label=mood,
            properties={},
        )
        self._store.add_node(node)
        return node

    def _ensure_capability(self, capability: str) -> Node:
        """Ensure a capability node exists."""
        node_id = f"cap:{capability}"
        node = self._store.get_node(node_id)
        if node:
            return node
        
        node = Node(
            id=node_id,
            type=NodeType.CAPABILITY,
            label=capability,
            properties={"capability": capability},
        )
        self._store.add_node(node)
        return node

    def _ensure_tag(self, tag: str) -> Node:
        """Ensure a tag node exists."""
        node_id = f"tag:{tag}"
        node = self._store.get_node(node_id)
        if node:
            return node
        
        node = Node(
            id=node_id,
            type=NodeType.TAG,
            label=tag,
            properties={"tag": tag},
        )
        self._store.add_node(node)
        return node

    # ==================== Zone Management ====================

    def upsert_zone(
        self,
        zone_id: str,
        label: Optional[str] = None,
        area_ids: Optional[list[str]] = None,
        properties: Optional[dict[str, Any]] = None,
    ) -> Node:
        """Create or update a zone node.
        
        Args:
            zone_id: Zone ID (e.g., "habitus_zone_west")
            label: Human-readable label
            area_ids: List of area IDs that belong to this zone
            properties: Additional properties
        
        Returns:
            The created/updated Node
        """
        now = int(time.time() * 1000)
        
        zone_node = Node(
            id=zone_id,
            type=NodeType.ZONE,
            label=label or zone_id,
            properties=properties or {},
            updated_at=now,
        )
        self._store.add_node(zone_node)
        
        # Create edges from areas to zone
        if area_ids:
            for area_id in area_ids:
                self._ensure_area(area_id)
                self._store.add_edge(Edge(
                    source=area_id,
                    target=zone_id,
                    type=EdgeType.BELONGS_TO,
                    weight=1.0,
                    confidence=1.0,
                    source_type="explicit",
                ))
        
        _LOGGER.debug("Upserted zone %s with %d areas", zone_id, len(area_ids or []))
        return zone_node

    # ==================== Mood Management ====================

    def upsert_mood(
        self,
        mood: str,
        label: Optional[str] = None,
        properties: Optional[dict[str, Any]] = None,
    ) -> Node:
        """Create or update a mood node.
        
        Args:
            mood: Mood name (e.g., "relax", "focus", "active")
            label: Human-readable label
            properties: Additional properties
        
        Returns:
            The created/updated Node
        """
        node_id = f"mood:{mood}"
        
        mood_node = Node(
            id=node_id,
            type=NodeType.MOOD,
            label=label or mood,
            properties=properties or {},
        )
        self._store.add_node(mood_node)
        
        _LOGGER.debug("Upserted mood %s", mood)
        return mood_node

    def relate_entity_to_mood(
        self,
        entity_id: str,
        mood: str,
        weight: float = 0.5,
        confidence: float = 0.5,
        evidence: Optional[dict[str, Any]] = None,
    ) -> Edge:
        """Create a relationship between an entity and a mood.
        
        Args:
            entity_id: Entity ID
            mood: Mood name
            weight: Edge weight
            confidence: Confidence score
            evidence: Supporting evidence
        
        Returns:
            The created Edge
        """
        self._ensure_mood(mood)
        
        edge = Edge(
            source=entity_id,
            target=f"mood:{mood}",
            type=EdgeType.RELATES_TO_MOOD,
            weight=weight,
            confidence=confidence,
            source_type="learned",
            evidence=evidence or {},
        )
        self._store.add_edge(edge)
        
        _LOGGER.debug("Related entity %s to mood %s (weight=%.2f, conf=%.2f)",
                     entity_id, mood, weight, confidence)
        return edge

    # ==================== Time Context ====================

    def upsert_time_context(
        self,
        context: str,
        label: Optional[str] = None,
        properties: Optional[dict[str, Any]] = None,
    ) -> Node:
        """Create or update a time context node.
        
        Args:
            context: Context name (e.g., "morning", "evening", "weekday")
            label: Human-readable label
            properties: Additional properties
        
        Returns:
            The created/updated Node
        """
        node_id = f"time:{context}"
        
        context_node = Node(
            id=node_id,
            type=NodeType.TIME_CONTEXT,
            label=label or context,
            properties=properties or {},
        )
        self._store.add_node(context_node)
        
        return context_node

    # ==================== Bulk Operations ====================

    def build_from_ha_states(
        self,
        states: list[dict[str, Any]],
        area_registry: Optional[dict[str, str]] = None,
        entity_registry: Optional[dict[str, dict[str, Any]]] = None,
    ) -> dict[str, int]:
        """Build graph from Home Assistant states.
        
        Args:
            states: List of HA state dictionaries
            area_registry: Mapping of area_id to area_name
            entity_registry: Mapping of entity_id to entity metadata
        
        Returns:
            Statistics about what was built
        """
        stats = {
            "entities": 0,
            "domains": 0,
            "areas": 0,
            "capabilities": 0,
            "edges": 0,
        }
        
        for state in states:
            entity_id = state.get("entity_id", "")
            if not entity_id:
                continue
            
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            
            # Get entity metadata
            entity_meta = (entity_registry or {}).get(entity_id, {})
            area_id = entity_meta.get("area_id")
            capabilities = entity_meta.get("capabilities", [])
            tags = entity_meta.get("tags", [])
            
            # Extract capabilities from attributes
            attrs = state.get("attributes", {})
            if attrs.get("supported_features"):
                # Parse supported_features into capabilities
                pass
            
            # Create entity node
            self.upsert_entity(
                entity_id=entity_id,
                domain=domain,
                label=state.get("attributes", {}).get("friendly_name", entity_id),
                area_id=area_id,
                capabilities=capabilities,
                tags=tags,
                properties={
                    "state": state.get("state"),
                    "last_changed": state.get("last_changed"),
                },
            )
            stats["entities"] += 1
        
        # Get final stats
        store_stats = self._store.stats()
        stats["domains"] = store_stats.get("nodes_by_type", {}).get("domain", 0)
        stats["areas"] = store_stats.get("nodes_by_type", {}).get("area", 0)
        stats["capabilities"] = store_stats.get("nodes_by_type", {}).get("cap", 0)
        stats["edges"] = store_stats.get("edge_count", 0)
        
        _LOGGER.info("Built graph from %d states: %s", len(states), stats)
        return stats

    def clear_cache(self) -> None:
        """Clear internal caches."""
        self._entity_cache.clear()
        self._area_cache.clear()
        self._domain_cache.clear()