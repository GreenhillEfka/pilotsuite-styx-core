"""Knowledge Graph Schema (P1-005).

Implements Neo4j/NetworkX schema for PilotSuite entities:
Nodes: Device, Zone, Habit, User, Action
Edges: located_in, triggers, depends_on, part_of
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

_LOGGER = logging.getLogger(__name__)

@dataclass
class KGNode:
    """Generic Knowledge Graph Node."""
    id: str
    type: str # "device", "zone", "habit", "user", "action"
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class KGEdge:
    """Generic Knowledge Graph Edge."""
    source: str # node.id
    target: str # node.id
    relation: str # "located_in", "triggers", etc.
    properties: Dict[str, Any] = field(default_factory=dict)

class KnowledgeGraphSchema:
    """Manages the canonical schema for the brain graph."""
    
    NODE_TYPES = {"device", "zone", "habit", "user", "action"}
    RELATION_TYPES = {"located_in", "triggers", "depends_on", "part_of", "caused_by"}
    
    def __init__(self):
        self.nodes: Dict[str, KGNode] = {}
        self.edges: List[KGEdge] = []
        self._index: Dict[str, Set[str]] = {t: set() for t in self.NODE_TYPES}

    def add_node(self, node: KGNode):
        """Adds a node to the graph."""
        self.nodes[node.id] = node
        self._index[node.type].add(node.id)
        _LOGGER.debug("Added node: %s (%s)", node.id, node.type)

    def add_edge(self, edge: KGEdge):
        """Adds an edge between existing nodes."""
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError("Edge references non-existent node")
        self.edges.append(edge)
        _LOGGER.debug("Added edge: %s -> %s [%s]", edge.source, edge.target, edge.relation)

    def sparql_query(self, query: str) -> List[Dict[str, Any]]:
        """Naive SPARQL-like query processor (subset)."""
        # Example: SELECT ?device WHERE { ?device located_in "zone_living" }
        results = []
        if "SELECT" in query and "WHERE" in query:
            parts = query.split("WHERE")
            select_vars = parts[0].replace("SELECT", "").strip().split()
            where_clause = parts[1].strip("{} ").split()
            
            if len(where_clause) >= 3:
                predicate = where_clause[1]
                obj = where_clause[2].strip('"')
                
                for edge in self.edges:
                    if edge.relation == predicate and edge.target == obj:
                        result = {}
                        for var in select_vars:
                            if "?" in var:
                                var_name = var.strip("?")
                                if var_name == "device":
                                    result[var_name] = edge.source
                        if result:
                            results.append(result)
        return results

# Global Instance
_kg_schema: Optional[KnowledgeGraphSchema] = None

def get_kg_schema() -> KnowledgeGraphSchema:
    global _kg_schema
    if _kg_schema is None:
        _kg_schema = KnowledgeGraphSchema()
        # Bootstrap with core entities
        _kg_schema.add_node(KGNode("zone_living", "zone", {"name": "Wohnzimmer"}))
        _kg_schema.add_node(KGNode("sensor.motion_1", "device", {"type": "motion"}))
        _kg_schema.add_edge(KGEdge("sensor.motion_1", "zone_living", "located_in"))
    return _kg_schema

# API Integration
def init_kg_api(bp):
    @bp.route("/brain/kg/query", methods=["POST"])
    def kg_sparql_query():
        import flask
        data = flask.request.get_json() or {}
        query = data.get("sparql", "")
        schema = get_kg_schema()
        results = schema.sparql_query(query)
        return {"ok": True, "results": results, "query": query}
