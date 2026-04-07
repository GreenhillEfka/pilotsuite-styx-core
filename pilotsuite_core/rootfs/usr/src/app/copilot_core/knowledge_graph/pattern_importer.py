"""Pattern Importer for Knowledge Graph.

Imports Habitus A→B rules as PATTERN nodes with TRIGGERS edges.
Connects patterns to entities, moods, and time contexts.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .models import Edge, EdgeType, Node, NodeType
from .graph_store import GraphStore, get_graph_store
from .builder import GraphBuilder

_LOGGER = logging.getLogger(__name__)


class PatternImporter:
    """Imports Habitus patterns into the Knowledge Graph."""

    def __init__(
        self,
        store: Optional[GraphStore] = None,
        builder: Optional[GraphBuilder] = None,
    ) -> None:
        """Initialize the pattern importer.
        
        Args:
            store: GraphStore instance (uses singleton if None)
            builder: GraphBuilder instance (creates new if None)
        """
        self._store = store or get_graph_store()
        self._builder = builder or GraphBuilder(store)
        self._pattern_cache: dict[str, Node] = {}

    def import_pattern(
        self,
        pattern_id: str,
        antecedent: str,
        consequent: str,
        confidence: float,
        support: int,
        lift: float,
        time_window_sec: int,
        observation_period_days: int = 0,
        evidence: Optional[dict[str, Any]] = None,
        time_contexts: Optional[list[str]] = None,
        mood_correlations: Optional[dict[str, float]] = None,
    ) -> Node:
        """Import a single A→B pattern into the graph.
        
        Args:
            pattern_id: Unique pattern identifier
            antecedent: Antecedent entity/transition (A) - e.g., "light.kitchen:on"
            consequent: Consequent entity/transition (B) - e.g., "light.livingroom:on"
            confidence: Confidence score P(B|A)
            support: Number of times this pattern was observed (nAB)
            lift: Lift ratio (confidence / baseline)
            time_window_sec: Time window in seconds
            observation_period_days: Days of observation
            evidence: Additional evidence data
            time_contexts: List of time contexts when this pattern is active
            mood_correlations: Mapping of mood -> correlation score
        
        Returns:
            The created PATTERN node
        """
        now = int(time.time() * 1000)
        
        # Create pattern node
        pattern_node = Node(
            id=pattern_id,
            type=NodeType.PATTERN,
            label=f"{antecedent} → {consequent}",
            properties={
                "antecedent": antecedent,
                "consequent": consequent,
                "confidence": confidence,
                "support": support,
                "lift": lift,
                "time_window_sec": time_window_sec,
                "observation_period_days": observation_period_days,
            },
            updated_at=now,
        )
        self._store.add_node(pattern_node)
        self._pattern_cache[pattern_id] = pattern_node
        
        # Parse entities from antecedent/consequent
        ant_entity = self._parse_entity(antecedent)
        con_entity = self._parse_entity(consequent)
        
        # Ensure entities exist (without full metadata)
        if ant_entity:
            self._ensure_entity_exists(ant_entity)
        if con_entity:
            self._ensure_entity_exists(con_entity)
        
        # Create TRIGGERS edge: antecedent → consequent
        self._store.add_edge(Edge(
            source=ant_entity or antecedent,
            target=con_entity or consequent,
            type=EdgeType.TRIGGERS,
            weight=confidence,
            confidence=confidence,
            source_type="learned",
            evidence={
                "pattern_id": pattern_id,
                "support": support,
                "lift": lift,
                "time_window_sec": time_window_sec,
                **(evidence or {}),
            },
        ))
        
        # Create edge from pattern to entities
        if ant_entity:
            self._store.add_edge(Edge(
                source=pattern_id,
                target=ant_entity,
                type=EdgeType.CORRELATES_WITH,
                weight=confidence,
                confidence=confidence,
                source_type="learned",
            ))
        
        if con_entity:
            self._store.add_edge(Edge(
                source=pattern_id,
                target=con_entity,
                type=EdgeType.CORRELATES_WITH,
                weight=confidence,
                confidence=confidence,
                source_type="learned",
            ))
        
        # Create time context relationships
        if time_contexts:
            for ctx in time_contexts:
                self._builder.upsert_time_context(ctx)
                self._store.add_edge(Edge(
                    source=pattern_id,
                    target=f"time:{ctx}",
                    type=EdgeType.ACTIVE_DURING,
                    weight=1.0,
                    confidence=1.0,
                    source_type="inferred",
                ))
        
        # Create mood correlations
        if mood_correlations:
            for mood, score in mood_correlations.items():
                self._builder.upsert_mood(mood)
                self._store.add_edge(Edge(
                    source=pattern_id,
                    target=f"mood:{mood}",
                    type=EdgeType.RELATES_TO_MOOD,
                    weight=score,
                    confidence=score,
                    source_type="learned",
                ))
        
        _LOGGER.debug(
            "Imported pattern %s: %s → %s (conf=%.2f, support=%d, lift=%.2f)",
            pattern_id, antecedent, consequent, confidence, support, lift
        )
        return pattern_node

    def _parse_entity(self, transition: str) -> Optional[str]:
        """Parse entity ID from a transition string like 'light.kitchen:on'."""
        if ":" in transition:
            return transition.split(":")[0]
        return transition if "." in transition else None

    def _ensure_entity_exists(self, entity_id: str) -> Node:
        """Ensure an entity node exists (with minimal metadata)."""
        existing = self._store.get_node(entity_id)
        if existing:
            return existing
        
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
        return self._builder.upsert_entity(
            entity_id=entity_id,
            domain=domain,
            label=entity_id,
        )

    def import_from_habitus_rules(
        self,
        rules: list[dict[str, Any]],
        min_confidence: float = 0.5,
        min_support: int = 5,
        min_lift: float = 1.2,
    ) -> dict[str, int]:
        """Import multiple rules from Habitus miner output.
        
        Args:
            rules: List of rule dictionaries from habitus_miner
            min_confidence: Minimum confidence threshold
            min_support: Minimum support threshold
            min_lift: Minimum lift threshold
        
        Returns:
            Statistics about import
        """
        stats = {
            "total_rules": len(rules),
            "imported": 0,
            "skipped_low_confidence": 0,
            "skipped_low_support": 0,
            "skipped_low_lift": 0,
            "patterns_created": 0,
            "edges_created": 0,
        }
        
        initial_stats = self._store.stats()
        initial_edges = initial_stats.get("edge_count", 0)
        
        for i, rule in enumerate(rules):
            # Extract rule fields
            antecedent = rule.get("A", "")
            consequent = rule.get("B", "")
            confidence = rule.get("confidence", 0.0)
            support = rule.get("nAB", rule.get("support", 0))
            lift = rule.get("lift", 1.0)
            time_window_sec = rule.get("dt_sec", rule.get("time_window_sec", 120))
            observation_period_days = rule.get("observation_period_days", 0)
            evidence = rule.get("evidence", {})
            
            # Apply filters
            if confidence < min_confidence:
                stats["skipped_low_confidence"] += 1
                continue
            if support < min_support:
                stats["skipped_low_support"] += 1
                continue
            if lift < min_lift:
                stats["skipped_low_lift"] += 1
                continue
            
            # Generate pattern ID
            pattern_id = f"pattern:{antecedent}:{consequent}:{time_window_sec}"
            
            # Extract time contexts from evidence
            time_contexts = self._extract_time_contexts(evidence)
            
            # Import pattern
            self.import_pattern(
                pattern_id=pattern_id,
                antecedent=antecedent,
                consequent=consequent,
                confidence=confidence,
                support=support,
                lift=lift,
                time_window_sec=time_window_sec,
                observation_period_days=observation_period_days,
                evidence=evidence,
                time_contexts=time_contexts,
            )
            stats["imported"] += 1
        
        final_stats = self._store.stats()
        stats["patterns_created"] = final_stats.get("nodes_by_type", {}).get("pattern", 0)
        stats["edges_created"] = final_stats.get("edge_count", 0) - initial_edges
        
        _LOGGER.info("Imported %d/%d patterns: %s", stats["imported"], stats["total_rules"], stats)
        return stats

    def _extract_time_contexts(self, evidence: dict[str, Any]) -> list[str]:
        """Extract time contexts from evidence data."""
        contexts = []
        
        # Check for time-of-day patterns
        if evidence.get("peak_hour"):
            hour = evidence["peak_hour"]
            if 5 <= hour < 12:
                contexts.append("morning")
            elif 12 <= hour < 18:
                contexts.append("afternoon")
            elif 18 <= hour < 22:
                contexts.append("evening")
            else:
                contexts.append("night")
        
        # Check for weekday patterns
        if evidence.get("weekday_pattern"):
            contexts.append("weekday")
        
        if evidence.get("weekend_pattern"):
            contexts.append("weekend")
        
        return contexts

    def get_patterns_for_entity(
        self,
        entity_id: str,
        min_confidence: float = 0.5,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get all patterns involving a specific entity.
        
        Args:
            entity_id: Entity ID to query
            min_confidence: Minimum confidence threshold
            limit: Maximum number of results
        
        Returns:
            List of pattern dictionaries
        """
        patterns = []
        
        # Get edges from this entity (antecedent patterns)
        out_edges = self._store.get_edges_from(entity_id, EdgeType.TRIGGERS)
        out_edges = [e for e in out_edges if e.confidence >= min_confidence]
        out_edges = sorted(out_edges, key=lambda e: e.confidence, reverse=True)[:limit]
        
        for edge in out_edges:
            pattern = self._find_pattern_for_edge(edge)
            if pattern:
                patterns.append({
                    "pattern_id": pattern.id,
                    "antecedent": entity_id,
                    "consequent": edge.target,
                    "confidence": edge.confidence,
                    "lift": edge.evidence.get("lift", 1.0),
                    "support": edge.evidence.get("support", 0),
                    "type": "triggers",
                })
        
        # Get edges to this entity (consequent patterns)
        in_edges = self._store.get_edges_to(entity_id, EdgeType.TRIGGERS)
        in_edges = [e for e in in_edges if e.confidence >= min_confidence]
        in_edges = sorted(in_edges, key=lambda e: e.confidence, reverse=True)[:limit]
        
        for edge in in_edges:
            pattern = self._find_pattern_for_edge(edge)
            if pattern:
                patterns.append({
                    "pattern_id": pattern.id,
                    "antecedent": edge.source,
                    "consequent": entity_id,
                    "confidence": edge.confidence,
                    "lift": edge.evidence.get("lift", 1.0),
                    "support": edge.evidence.get("support", 0),
                    "type": "triggered_by",
                })
        
        return patterns[:limit]

    def _find_pattern_for_edge(self, edge: Edge) -> Optional[Node]:
        """Find the PATTERN node associated with a TRIGGERS edge."""
        # Pattern ID format: pattern:antecedent:consequent:time_window
        if edge.evidence and "pattern_id" in edge.evidence:
            return self._store.get_node(edge.evidence["pattern_id"])
        
        # Fallback: search by label
        # Note: For production, implement index-based lookup on pattern labels
        return None

    def clear_cache(self) -> None:
        """Clear internal caches."""
        self._pattern_cache.clear()