"""Data models for Knowledge Graph.

Defines node types, edge types, and data structures for the graph.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class NodeType(Enum):
    """Types of nodes in the Knowledge Graph."""
    ENTITY = "entity"          # light.kitchen, sensor.temperature
    DOMAIN = "domain"          # light, sensor, switch
    AREA = "area"              # Wohnzimmer, Küche
    ZONE = "zone"              # habitus_zone_west
    PATTERN = "pattern"        # A→B rule from Habitus
    MOOD = "mood"              # relax, focus, active
    CAPABILITY = "cap"         # dimmable, color_temp
    TAG = "tag"                # aicp.place.kueche
    TIME_CONTEXT = "time"      # morning, evening, weekday
    USER = "user"              # Multi-user support (future)


class EdgeType(Enum):
    """Types of edges (relationships) in the Knowledge Graph."""
    # Hierarchical
    BELONGS_TO = "belongs_to"        # Entity → Area, Area → Zone
    HAS_CAPABILITY = "has_cap"       # Entity → Capability
    HAS_TAG = "has_tag"              # Entity → Tag
    
    # Causal (from Habitus)
    TRIGGERS = "triggers"            # Pattern A → B
    CORRELATES_WITH = "correlates"   # Statistical correlation
    
    # Contextual
    ACTIVE_DURING = "active_during"  # Pattern → TimeContext
    RELATES_TO_MOOD = "relates_mood" # Entity/Pattern → Mood
    
    # User-specific (future)
    PREFERRED_BY = "preferred_by"    # Entity/Pattern → User
    AVOIDED_BY = "avoided_by"        # Entity/Pattern → User


@dataclass
class Node:
    """A node in the Knowledge Graph."""
    id: str                          # Unique identifier
    type: NodeType                   # Node type
    label: str                       # Human-readable label
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = field(default_factory=lambda: int(time.time() * 1000))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "properties": self.properties,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        return cls(
            id=data["id"],
            type=NodeType(data["type"]),
            label=data["label"],
            properties=data.get("properties", {}),
            created_at=data.get("created_at", int(time.time() * 1000)),
            updated_at=data.get("updated_at", int(time.time() * 1000)),
        )


@dataclass
class Edge:
    """An edge (relationship) in the Knowledge Graph."""
    source: str                      # Source node ID
    target: str                      # Target node ID
    type: EdgeType                   # Edge type
    weight: float = 1.0              # Edge weight (0.0 - 1.0)
    confidence: float = 0.0          # Confidence score (0.0 - 1.0)
    source_type: str = "inferred"    # "explicit", "inferred", "learned"
    evidence: dict[str, Any] = field(default_factory=dict)  # Supporting evidence
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = field(default_factory=lambda: int(time.time() * 1000))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "weight": self.weight,
            "confidence": self.confidence,
            "source_type": self.source_type,
            "evidence": self.evidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Edge":
        return cls(
            source=data["source"],
            target=data["target"],
            type=EdgeType(data["type"]),
            weight=data.get("weight", 1.0),
            confidence=data.get("confidence", 0.0),
            source_type=data.get("source_type", "inferred"),
            evidence=data.get("evidence", {}),
            created_at=data.get("created_at", int(time.time() * 1000)),
            updated_at=data.get("updated_at", int(time.time() * 1000)),
        )
    
    @property
    def id(self) -> str:
        """Generate unique edge ID from source, target, and type."""
        return f"{self.source}:{self.type.value}:{self.target}"


@dataclass
class GraphQuery:
    """A query against the Knowledge Graph."""
    query_type: str                  # "semantic", "structural", "causal", "temporal", "contextual"
    entity_id: Optional[str] = None
    zone_id: Optional[str] = None
    mood: Optional[str] = None
    time_context: Optional[str] = None
    pattern_id: Optional[str] = None
    max_results: int = 10
    min_confidence: float = 0.5
    include_evidence: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "query_type": self.query_type,
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "mood": self.mood,
            "time_context": self.time_context,
            "pattern_id": self.pattern_id,
            "max_results": self.max_results,
            "min_confidence": self.min_confidence,
            "include_evidence": self.include_evidence,
        }


@dataclass
class GraphResult:
    """Result from a Knowledge Graph query."""
    nodes: list[Node]
    edges: list[Edge]
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "confidence": self.confidence,
            "sources": self.sources,
            "evidence": self.evidence,
        }