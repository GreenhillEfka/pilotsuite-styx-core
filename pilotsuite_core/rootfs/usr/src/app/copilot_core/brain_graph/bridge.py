"""
Graph Candidates Bridge - Connect Brain Graph patterns to Candidates Store.

This module provides a clean bridge between Brain Graph v2 and the Candidates Store:
1. Extract high-value correlation edges from brain graph
2. Transform graph entities into candidate-friendly format
3. Provide pattern extraction helpers for Habitus miner

The bridge isolates graph-specific logic from candidate creation,
making it easy to modify pattern detection without affecting candidates.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Literal
from datetime import datetime

from ..brain_graph.model import GraphNode, GraphEdge, EdgeType
from ..brain_graph.service import BrainGraphService


# Candidate pattern types
CandidatePatternType = Literal["habitus", "zone_activity", "scene", "routine"]

# Privacy patterns for redaction
PII_PATTERNS = [
    re.compile(r'\b[\w._%+-]+@[\w.-]+\.[A-Z|a-z]{2,}\b'),  # emails
    re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),            # IP addresses
    re.compile(r'\b\d{3}-?\d{3}-?\d{4}\b'),                # phone numbers
]


@dataclass
class CandidatePattern:
    """A pattern extracted from brain graph ready for candidate creation."""
    
    pattern_id: str              # Stable identifier (e.g., "habitus__light.kitchen__on→switch.coffee__on")
    pattern_type: CandidatePatternType
    antecedent: Dict[str, Any]   # Trigger: {service, entity, state_change}
    consequent: Dict[str, Any]   # Action: {service, entity, state_change}
    evidence: Dict[str, Any]     # {confidence, support, lift, count}
    graph_context: Dict[str, Any]  # {nodes: [...], edges: [...]}
    created_at_ms: int
    source_edge_types: List[str]  # Which edge types contributed to this pattern
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "antecedent": self.antecedent,
            "consequent": self.consequent,
            "evidence": self.evidence,
            "graph_context": self.graph_context,
            "created_at_ms": self.created_at_ms,
            "source_edge_types": self.source_edge_types
        }


@dataclass
class PatternExtractionConfig:
    """Configuration for pattern extraction from brain graph."""
    # Minimum edge weight to consider
    min_edge_weight: float = 0.5
    # Maximum patterns to extract
    max_patterns: int = 50
    # Minimum confidence for patterns
    min_confidence: float = 0.6
    # Lookback time in hours
    lookback_hours: int = 72
    # Edge types to include
    include_edge_types: List[str] = field(default_factory=lambda: ["affects", "correlates", "triggered_by"])
    # Edge types to exclude (too noisy)
    exclude_edge_types: List[str] = field(default_factory=lambda: ["observed_with", "mentions"])
    # Domain allowlist (empty = all)
    domain_allowlist: List[str] = field(default_factory=list)
    # Domain blocklist (sensitive domains)
    domain_blocklist: List[str] = field(default_factory=lambda: ["lock", "alarm", "cover"])  # covers can be annoying


class GraphCandidatesBridge:
    """
    Bridge between Brain Graph v2 and Candidates Store.
    
    Provides clean methods to:
    - Extract candidate-ready patterns from brain graph
    - Transform graph data into candidate schema
    - Query graph for related entities/context
    """
    
    def __init__(
        self,
        brain_service: BrainGraphService,
        config: Optional[PatternExtractionConfig] = None
    ):
        """
        Initialize the bridge.
        
        Args:
            brain_service: BrainGraphService instance for graph access
            config: Optional configuration for pattern extraction
        """
        self.brain_service = brain_service
        self.config = config or PatternExtractionConfig()
    
    def extract_candidate_patterns(
        self,
        pattern_type: CandidatePatternType = "habitus",
        include_graph_context: bool = True
    ) -> List[CandidatePattern]:
        """
        Extract candidate-ready patterns from brain graph.
        
        Args:
            pattern_type: Type of patterns to extract
            include_graph_context: Include related nodes/edges in context
            
        Returns:
            List of CandidatePattern objects ready for candidate creation
        """
        patterns = []
        now_ms = int(time.time() * 1000)
        
        if pattern_type == "habitus":
            patterns = self._extract_habitus_patterns(now_ms, include_graph_context)
        elif pattern_type == "zone_activity":
            patterns = self._extract_zone_activity_patterns(now_ms, include_graph_context)
        elif pattern_type == "scene":
            patterns = self._extract_scene_patterns(now_ms, include_graph_context)
        elif pattern_type == "routine":
            patterns = self._extract_routine_patterns(now_ms, include_graph_context)
        
        # Apply max_patterns limit
        return patterns[:self.config.max_patterns]
    
    def _extract_habitus_patterns(
        self,
        now_ms: int,
        include_context: bool
    ) -> List[CandidatePattern]:
        """Extract A→B habitus patterns from graph edges."""
        patterns: Dict[str, CandidatePattern] = {}
        
        # Get all relevant edges
        all_edges = self.brain_service.store.get_edges()
        
        for edge in all_edges:
            # Filter by edge type
            if edge.edge_type not in self.config.include_edge_types:
                continue
            if edge.edge_type in self.config.exclude_edge_types:
                continue
            
            # Apply weight threshold
            effective_weight = edge.effective_weight(now_ms, self.brain_service.edge_half_life_hours)
            if effective_weight < self.config.min_edge_weight:
                continue
            
            # Parse edge endpoints
            from_parts = self._parse_node_id(edge.from_node)
            to_parts = self._parse_node_id(edge.to_node)
            
            if not from_parts or not to_parts:
                continue
            
            # Skip if domain is blocked
            if from_parts.get("domain") in self.config.domain_blocklist:
                continue
            if to_parts.get("domain") in self.config.domain_blocklist:
                continue
            
            # Skip if entity IDs contain personal info
            if self._contains_pii(from_parts.get("id", "")) or self._contains_pii(to_parts.get("id", "")):
                continue
            
            # Create pattern ID
            antecedent = f"{from_parts.get('service', 'unknown')}:{from_parts.get('id', '')}"
            consequent = f"{to_parts.get('service', 'unknown')}:{to_parts.get('id', '')}"
            pattern_id = self._generate_pattern_id("habitus", antecedent, consequent)
            
            # Calculate evidence from edge weight
            evidence = {
                "confidence": min(1.0, effective_weight / 2.0),  # Normalize to 0-1
                "support": effective_weight,
                "lift": effective_weight,  # Simplified lift for v0
                "count": int(effective_weight * 5),  # Estimate count from weight
                "edge_weight": effective_weight
            }
            
            # Get graph context
            graph_context = {}
            if include_context:
                nodes, edges = self.brain_service.store.get_neighborhood(
                    edge.from_node, hops=1
                )
                graph_context = {
                    "nodes": [{"id": n.id, "kind": n.kind, "label": n.label} for n in nodes],
                    "edges": [{"id": e.id, "from": e.from_node, "to": e.to_node, "type": e.edge_type} for e in edges[:10]]
                }
            
            patterns[pattern_id] = CandidatePattern(
                pattern_id=pattern_id,
                pattern_type="habitus",
                antecedent={
                    "service": from_parts.get("service", "unknown"),
                    "entity": from_parts.get("id", ""),
                    "full": antecedent,
                    "kind": from_parts.get("kind", "entity"),
                    "domain": from_parts.get("domain", None)
                },
                consequent={
                    "service": to_parts.get("service", "unknown"),
                    "entity": to_parts.get("id", ""),
                    "full": consequent,
                    "kind": to_parts.get("kind", "entity"),
                    "domain": to_parts.get("domain", None)
                },
                evidence=evidence,
                graph_context=graph_context,
                created_at_ms=now_ms,
                source_edge_types=[edge.edge_type]
            )
        
        return list(patterns.values())
    
    def _extract_zone_activity_patterns(
        self,
        now_ms: int,
        include_context: bool
    ) -> List[CandidatePattern]:
        """Extract zone-based activity patterns."""
        patterns: Dict[str, CandidatePattern] = {}
        
        # Get all zone edges
        all_edges = self.brain_service.store.get_edges()
        zone_edges = [e for e in all_edges if e.edge_type == "in_zone"]
        
        for edge in zone_edges:
            effective_weight = edge.effective_weight(now_ms, self.brain_service.edge_half_life_hours)
            if effective_weight < self.config.min_edge_weight:
                continue
            
            # Get entity node
            entity_node = self.brain_service.store.get_node(edge.from_node)
            zone_node = self.brain_service.store.get_node(edge.to_node)
            
            if not entity_node or not zone_node:
                continue
            
            # Parse entity
            entity_parts = self._parse_node_id(edge.from_node)
            zone_name = zone_node.label if zone_node else edge.to_node
            
            pattern_id = self._generate_pattern_id(
                "zone_activity",
                f"zone:{zone_name}",
                f"{entity_parts.get('service', 'unknown')}:{entity_parts.get('id', '')}"
            )
            
            patterns[pattern_id] = CandidatePattern(
                pattern_id=pattern_id,
                pattern_type="zone_activity",
                antecedent={
                    "zone": zone_name,
                    "zone_id": edge.to_node
                },
                consequent={
                    "service": entity_parts.get("service", "unknown"),
                    "entity": entity_parts.get("id", ""),
                    "kind": entity_parts.get("kind", "entity"),
                    "domain": entity_parts.get("domain", None)
                },
                evidence={
                    "confidence": min(1.0, effective_weight),
                    "support": effective_weight,
                    "lift": effective_weight,
                    "count": int(effective_weight * 3)
                },
                graph_context={},
                created_at_ms=now_ms,
                source_edge_types=["in_zone"]
            )
        
        return list(patterns.values())
    
    def _extract_scene_patterns(
        self,
        now_ms: int,
        include_context: bool
    ) -> List[CandidatePattern]:
        """Extract multi-device scene patterns (co-activated entities)."""
        patterns: Dict[str, CandidatePattern] = {}

        all_edges = self.brain_service.store.get_edges()
        # Co-occurrence edges indicate devices activated together
        co_edges = [
            e for e in all_edges
            if e.edge_type in ("correlates_with", "co_activated", "triggers")
        ]

        for edge in co_edges:
            effective_weight = edge.effective_weight(
                now_ms, self.brain_service.edge_half_life_hours
            )
            if effective_weight < self.config.min_edge_weight:
                continue

            from_node = self.brain_service.store.get_node(edge.from_node)
            to_node = self.brain_service.store.get_node(edge.to_node)
            if not from_node or not to_node:
                continue

            # Only scene patterns: multi-domain device groups
            from_parts = self._parse_node_id(edge.from_node)
            to_parts = self._parse_node_id(edge.to_node)
            if from_parts.get("kind") != "entity" or to_parts.get("kind") != "entity":
                continue

            pattern_id = self._generate_pattern_id(
                "scene", edge.from_node, edge.to_node
            )

            graph_context = {}
            if include_context:
                graph_context = {
                    "nodes": [
                        {"id": from_node.id, "kind": from_node.kind, "label": from_node.label},
                        {"id": to_node.id, "kind": to_node.kind, "label": to_node.label},
                    ],
                    "edges": [{"id": edge.id, "from": edge.from_node, "to": edge.to_node, "type": edge.edge_type}],
                }

            patterns[pattern_id] = CandidatePattern(
                pattern_id=pattern_id,
                pattern_type="scene",
                antecedent={
                    "entity": from_parts.get("id", ""),
                    "domain": from_parts.get("domain"),
                    "kind": "entity",
                },
                consequent={
                    "entity": to_parts.get("id", ""),
                    "domain": to_parts.get("domain"),
                    "kind": "entity",
                },
                evidence={
                    "confidence": min(1.0, effective_weight),
                    "support": effective_weight,
                    "lift": effective_weight,
                    "count": int(effective_weight * 3),
                },
                graph_context=graph_context,
                created_at_ms=now_ms,
                source_edge_types=[edge.edge_type],
            )

        return list(patterns.values())
    
    def _extract_routine_patterns(
        self,
        now_ms: int,
        include_context: bool
    ) -> List[CandidatePattern]:
        """Extract time-based routine patterns from service call nodes."""
        patterns: Dict[str, CandidatePattern] = {}

        all_edges = self.brain_service.store.get_edges()
        # Service→entity edges with "targets" type indicate intentional actions
        service_edges = [e for e in all_edges if e.edge_type == "targets"]

        for edge in service_edges:
            effective_weight = edge.effective_weight(
                now_ms, self.brain_service.edge_half_life_hours
            )
            if effective_weight < self.config.min_edge_weight:
                continue

            service_node = self.brain_service.store.get_node(edge.from_node)
            entity_node = self.brain_service.store.get_node(edge.to_node)
            if not service_node or not entity_node:
                continue

            # Only service→entity patterns
            from_parts = self._parse_node_id(edge.from_node)
            to_parts = self._parse_node_id(edge.to_node)
            if from_parts.get("kind") != "service":
                continue

            pattern_id = self._generate_pattern_id(
                "routine", edge.from_node, edge.to_node
            )

            graph_context = {}
            if include_context:
                graph_context = {
                    "nodes": [
                        {"id": service_node.id, "kind": service_node.kind, "label": service_node.label},
                        {"id": entity_node.id, "kind": entity_node.kind, "label": entity_node.label},
                    ],
                    "edges": [{"id": edge.id, "from": edge.from_node, "to": edge.to_node, "type": edge.edge_type}],
                }

            patterns[pattern_id] = CandidatePattern(
                pattern_id=pattern_id,
                pattern_type="routine",
                antecedent={
                    "service": from_parts.get("service", "unknown"),
                    "domain": from_parts.get("domain"),
                    "kind": "service",
                },
                consequent={
                    "entity": to_parts.get("id", ""),
                    "domain": to_parts.get("domain"),
                    "kind": "entity",
                },
                evidence={
                    "confidence": min(1.0, effective_weight),
                    "support": effective_weight,
                    "lift": effective_weight,
                    "count": int(effective_weight * 2),
                },
                graph_context=graph_context,
                created_at_ms=now_ms,
                source_edge_types=[edge.edge_type],
            )

        return list(patterns.values())
    
    def _parse_node_id(self, node_id: str) -> Dict[str, str]:
        """Parse a node ID into components."""
        result = {
            "id": node_id,
            "kind": "unknown",
            "service": None,
            "domain": None
        }
        
        # Entity nodes: ha.entity:light.kitchen
        if node_id.startswith("ha.entity:"):
            result["id"] = node_id[10:]  # Remove prefix
            result["kind"] = "entity"
            parts = result["id"].split(".")
            if len(parts) >= 2:
                result["domain"] = parts[0]
                result["service"] = f"{parts[0]}.{parts[1]}" if len(parts) > 1 else parts[0]
        
        # Service nodes: ha.service:light.turn_on
        elif node_id.startswith("ha.service:"):
            result["id"] = node_id[11:]
            result["kind"] = "service"
            result["service"] = result["id"]
            parts = result["id"].split(".")
            if len(parts) >= 1:
                result["domain"] = parts[0]
        
        # Zone nodes: zone:kitchen
        elif node_id.startswith("zone:"):
            result["id"] = node_id[5:]
            result["kind"] = "zone"
        
        # Device nodes: ha.device:abc123
        elif node_id.startswith("ha.device:"):
            result["id"] = node_id[10:]
            result["kind"] = "device"
        
        return result
    
    def _generate_pattern_id(self, pattern_type: str, antecedent: str, consequent: str) -> str:
        """Generate a stable pattern ID."""
        content = f"{pattern_type}:{antecedent}→{consequent}"
        short_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"{pattern_type}__{short_hash}"
    
    def _contains_pii(self, text: str) -> bool:
        """Check if text contains PII patterns."""
        for pattern in PII_PATTERNS:
            if pattern.search(text):
                return True
        return False
    
    def get_pattern_by_id(self, pattern_id: str) -> Optional[CandidatePattern]:
        """
        Get a specific pattern by ID.
        
        Args:
            pattern_id: The pattern ID to look up
            
        Returns:
            CandidatePattern if found, None otherwise
        """
        # Extract type and hash from pattern_id
        parts = pattern_id.split("__", 1)
        if len(parts) != 2:
            return None
        
        pattern_type = parts[0]
        patterns = self.extract_candidate_patterns(pattern_type=pattern_type)
        
        for pattern in patterns:
            if pattern.pattern_id == pattern_id:
                return pattern
        
        return None
    
    def get_pattern_evidence_for_candidate(
        self,
        pattern: CandidatePattern
    ) -> Dict[str, Any]:
        """
        Get evidence dict ready for candidate creation.
        
        Args:
            pattern: CandidatePattern to get evidence for
            
        Returns:
            Evidence dict suitable for CandidateStore.add_candidate()
        """
        return {
            "confidence": pattern.evidence.get("confidence", 0.5),
            "support": pattern.evidence.get("support", 0.1),
            "lift": pattern.evidence.get("lift", 1.0),
            "count": pattern.evidence.get("count", 1),
            "pattern_type": pattern.pattern_type,
            "source_edge_types": pattern.source_edge_types,
            "antecedent": pattern.antecedent,
            "consequent": pattern.consequent
        }
    
    def get_candidate_metadata(
        self,
        pattern: CandidatePattern,
        mood_context: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Get metadata dict ready for candidate creation.
        
        Args:
            pattern: CandidatePattern to get metadata for
            mood_context: Optional mood scores (comfort, frugality, joy)
            
        Returns:
            Metadata dict suitable for CandidateStore.add_candidate()
        """
        metadata = {
            "pattern_created_at": datetime.fromtimestamp(
                pattern.created_at_ms / 1000
            ).isoformat(),
            "source": "brain_graph_bridge_v1",
            "antecedent": pattern.antecedent,
            "consequent": pattern.consequent,
            "domains": [
                pattern.antecedent.get("domain"),
                pattern.consequent.get("domain")
            ]
        }
        
        # Add graph context if available
        if pattern.graph_context:
            context_summary = {
                "related_nodes": len(pattern.graph_context.get("nodes", [])),
                "related_edges": len(pattern.graph_context.get("edges", []))
            }
            metadata["graph_context_summary"] = context_summary
        
        # Add mood impact estimates
        if mood_context:
            metadata["mood_impact"] = self._estimate_mood_impact(pattern, mood_context)
        
        return metadata
    
    def _estimate_mood_impact(
        self,
        pattern: CandidatePattern,
        mood: Dict[str, float]
    ) -> Dict[str, float]:
        """Estimate mood impact of a pattern."""
        impact = {}
        
        # Comfort: higher for frequent actions, lower for complex sequences
        ant_domain = pattern.antecedent.get("domain", "")
        cons_domain = pattern.consequent.get("domain", "")
        
        if ant_domain in ["light", "switch"] and cons_domain in ["light", "switch"]:
            impact["comfort"] = min(1.0, mood.get("comfort", 0.5) + 0.2)
        elif ant_domain in ["media_player", "tv"]:
            impact["comfort"] = mood.get("comfort", 0.5)
        
        # Frugality: penalize HVAC, reward smart controls
        if cons_domain in ["climate", "heater", "ac"]:
            impact["frugality"] = max(0.0, mood.get("frugality", 0.5) - 0.1)
        elif cons_domain in ["light", "switch"]:
            impact["frugality"] = min(1.0, mood.get("frugality", 0.5) + 0.1)
        
        # Joy: reward ambient/scene patterns
        if cons_domain in ["light", "media_player"]:
            impact["joy"] = min(1.0, mood.get("joy", 0.5) + 0.15)
        
        return impact
    
    def get_related_entities(
        self,
        entity_id: str,
        hops: int = 2
    ) -> Dict[str, Any]:
        """
        Get related entities from brain graph for context.
        
        Args:
            entity_id: Entity ID to get relations for
            hops: How many hops to traverse
            
        Returns:
            Dict with 'entities', 'zones', 'services' keys
        """
        entity_node_id = f"ha.entity:{entity_id}"
        
        nodes, edges = self.brain_service.store.get_neighborhood(
            center_node=entity_node_id,
            hops=hops
        )
        
        related = {
            "entities": [],
            "zones": [],
            "services": [],
            "devices": []
        }
        
        for node in nodes:
            if node.id == entity_node_id:
                continue
            
            node_info = {
                "id": node.id,
                "label": node.label,
                "kind": node.kind,
                "score": node.score,
                "domain": node.domain
            }
            
            if node.kind == "entity":
                related["entities"].append(node_info)
            elif node.kind == "zone":
                related["zones"].append(node_info)
            elif node.kind == "device":
                related["devices"].append(node_info)
            elif node.kind == "concept" and node.id.startswith("ha.service:"):
                related["services"].append(node_info)
        
        return related


# Export for convenience
__all__ = [
    "GraphCandidatesBridge",
    "CandidatePattern",
    "PatternExtractionConfig",
]
