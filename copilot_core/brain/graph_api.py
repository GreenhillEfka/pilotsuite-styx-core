"""Brain Graph API — REST/GraphQL interface for knowledge graph operations.

Provides SPARQL-like query interface and CRUD operations for entities and relationships.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Any, Optional

from .graph_store import BrainGraphStore, Entity, Relationship, TemporalContext


class BrainGraphAPI:
    """API layer for knowledge graph operations.
    
    Supports:
    - Entity CRUD operations
    - Relationship management
    - SPARQL-like queries
    - Temporal reasoning
    - Graph traversal
    """
    
    def __init__(self, storage_path: Optional[str] = None,
                 neo4j_uri: Optional[str] = None,
                 neo4j_user: Optional[str] = None,
                 neo4j_password: Optional[str] = None):
        self.store = BrainGraphStore(
            storage_path=storage_path,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password
        )
    
    def add_entity(self, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add entity via API.
        
        Args:
            entity_data: Dict with keys: id, type, name, attributes, temporal
            
        Returns:
            Response dict with success status and entity_id
        """
        entity_id = entity_data.get("id")
        if not entity_id:
            return {"success": False, "error": "Entity ID required"}
        
        success = self.store.add_entity(entity_id, entity_data)
        
        return {
            "success": success,
            "entity_id": entity_id,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_entity(self, entity_id: str) -> Dict[str, Any]:
        """Retrieve entity via API."""
        entity = self.store.get_entity(entity_id)
        
        if entity:
            return {
                "success": True,
                "entity": entity
            }
        return {
            "success": False,
            "error": "Entity not found"
        }
    
    def delete_entity(self, entity_id: str) -> Dict[str, Any]:
        """Delete entity via API."""
        success = self.store.delete_entity(entity_id)
        
        return {
            "success": success,
            "entity_id": entity_id,
            "timestamp": datetime.now().isoformat()
        }
    
    def add_relationship(self, relationship_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add relationship via API.
        
        Args:
            relationship_data: Dict with keys: from, type, to, attributes
            
        Returns:
            Response dict with success status
        """
        from_entity = relationship_data.get("from")
        to_entity = relationship_data.get("to")
        rel_type = relationship_data.get("type", "related_to")
        attributes = relationship_data.get("attributes", {})
        
        if not from_entity or not to_entity:
            return {
                "success": False,
                "error": "Both 'from' and 'to' entities required"
            }
        
        success = self.store.add_relationship(
            from_entity, rel_type, to_entity, attributes
        )
        
        return {
            "success": success,
            "relationship": {
                "from": from_entity,
                "type": rel_type,
                "to": to_entity
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def query(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """Query entities via API.
        
        Supports:
        - type: Filter by entity type
        - name: Filter by name (partial match)
        - attributes: Filter by attribute values
        - temporal: Time-based filtering
        - sparql: Raw SPARQL-like query string
        """
        # Handle SPARQL-like queries
        if "sparql" in query_params:
            results = self.store.execute_sparql_like(query_params["sparql"])
            return {
                "success": True,
                "entities": results,
                "query_type": "sparql"
            }
        
        # Handle structured queries
        results = []
        entity_type = query_params.get("type")
        name_filter = query_params.get("name")
        attr_filter = query_params.get("attributes", {})
        
        if entity_type:
            results = self.store.query_by_type(entity_type)
        else:
            results = [e.to_dict() for e in self.store.entities.values()]
        
        # Apply filters
        if name_filter:
            results = [
                e for e in results 
                if name_filter.lower() in e.get("name", "").lower()
            ]
        
        if attr_filter:
            for key, value in attr_filter.items():
                results = [
                    e for e in results
                    if e.get("attributes", {}).get(key) == value
                ]
        
        return {
            "success": True,
            "entities": results,
            "count": len(results),
            "query_type": "structured"
        }
    
    def get_relationships(self, entity_id: str) -> Dict[str, Any]:
        """Get relationships for an entity."""
        relationships = self.store.get_relationships(entity_id)
        
        return {
            "success": True,
            "entity_id": entity_id,
            "relationships": relationships,
            "count": len(relationships)
        }
    
    def traverse(self, entity_id: str, relation_type: str, 
                max_depth: int = 1) -> Dict[str, Any]:
        """Traverse graph from an entity."""
        results = self.store.traverse_from(entity_id, relation_type, max_depth)
        
        return {
            "success": True,
            "start_entity": entity_id,
            "relation_type": relation_type,
            "max_depth": max_depth,
            "connected_entities": results,
            "count": len(results)
        }
    
    def temporal_query(self, entity_id: str, 
                      query_time: str) -> Dict[str, Any]:
        """Query entity state at a specific time.
        
        Args:
            entity_id: Entity to query
            query_time: ISO 8601 timestamp
            
        Returns:
            Entity state at the specified time (if temporal data exists)
        """
        from datetime import datetime as dt
        
        try:
            query_dt = dt.fromisoformat(query_time)
        except ValueError:
            return {
                "success": False,
                "error": "Invalid timestamp format. Use ISO 8601."
            }
        
        entity = self.store.get_entity(entity_id)
        if not entity:
            return {
                "success": False,
                "error": "Entity not found"
            }
        
        # Check temporal validity
        temporal = entity.get("temporal", {})
        if temporal:
            valid_from = temporal.get("valid_from")
            valid_to = temporal.get("valid_to")
            
            is_valid = True
            if valid_from and dt.fromisoformat(valid_from) > query_dt:
                is_valid = False
            if valid_to and dt.fromisoformat(valid_to) < query_dt:
                is_valid = False
            
            return {
                "success": is_valid,
                "entity": entity if is_valid else None,
                "query_time": query_time,
                "temporal_context": temporal
            }
        
        # No temporal data - return current state
        return {
            "success": True,
            "entity": entity,
            "query_time": query_time,
            "note": "No temporal context available"
        }
    
    def graph_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        stats = self.store.get_stats()
        
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    def export(self, format: str = "json") -> Dict[str, Any]:
        """Export graph data.
        
        Args:
            format: Export format (json, graphml)
            
        Returns:
            Exported data
        """
        if format.lower() == "json":
            data = self.store.export_to_json()
            return {
                "success": True,
                "format": "json",
                "data": data
            }
        elif format.lower() == "graphml":
            data = self.store.export_to_graphml()
            return {
                "success": True,
                "format": "graphml",
                "data": data
            }
        else:
            return {
                "success": False,
                "error": f"Unsupported format: {format}"
            }
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self.store.save()
    
    # Convenience methods for common patterns
    
    def find_path(self, from_entity: str, to_entity: str, 
                 max_depth: int = 5) -> Dict[str, Any]:
        """Find shortest path between two entities."""
        try:
            import networkx as nx
        except ImportError:
            return {
                "success": False,
                "error": "NetworkX not available"
            }
        
        if not self.store.graph:
            return {
                "success": False,
                "error": "Graph not initialized"
            }
        
        try:
            path = nx.shortest_path(
                self.store.graph, 
                source=from_entity, 
                target=to_entity
            )
            
            return {
                "success": True,
                "path": path,
                "length": len(path) - 1,
                "from": from_entity,
                "to": to_entity
            }
        except nx.NetworkXNoPath:
            return {
                "success": False,
                "error": "No path found",
                "from": from_entity,
                "to": to_entity
            }
    
    def get_subgraph(self, center_entity: str, 
                    radius: int = 2) -> Dict[str, Any]:
        """Extract subgraph around an entity."""
        try:
            import networkx as nx
        except ImportError:
            return {
                "success": False,
                "error": "NetworkX not available"
            }
        
        if not self.store.graph:
            return {
                "success": False,
                "error": "Graph not initialized"
            }
        
        # Get ego graph
        ego = nx.ego_graph(self.store.graph, center_entity, radius=radius)
        
        # Convert to dict
        nodes = {n: dict(ego.nodes[n]) for n in ego.nodes()}
        edges = [(u, v, dict(d)) for u, v, d in ego.edges(data=True)]
        
        return {
            "success": True,
            "center": center_entity,
            "radius": radius,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges)
        }


# GraphQL schema for knowledge graph
GRAPHQL_SCHEMA = """
type Entity {
    id: ID!
    type: String!
    name: String
    attributes: JSON
    temporal: TemporalContext
    createdAt: DateTime!
    updatedAt: DateTime!
}

type Relationship {
    from: Entity!
    type: String!
    to: Entity!
    attributes: JSON
    temporal: TemporalContext
}

type TemporalContext {
    validFrom: DateTime
    validTo: DateTime
    timestamp: DateTime!
}

type Query {
    entity(id: ID!): Entity
    entitiesByType(type: String!): [Entity!]!
    relationships(entityId: ID!): [Relationship!]!
    traverse(from: ID!, relationType: String!, maxDepth: Int): [Entity!]!
    sparql(query: String!): [JSON!]!
    temporalQuery(id: ID!, time: DateTime!): Entity
    graphStats: GraphStats!
}

type Mutation {
    addEntity(input: EntityInput!): Entity!
    updateEntity(id: ID!, input: EntityInput!): Entity!
    deleteEntity(id: ID!): Boolean!
    addRelationship(input: RelationshipInput!): Relationship!
    deleteRelationship(from: ID!, type: String!, to: ID!): Boolean!
}

input EntityInput {
    id: ID!
    type: String!
    name: String
    attributes: JSON
    temporal: TemporalInput
}

input RelationshipInput {
    from: ID!
    type: String!
    to: ID!
    attributes: JSON
}

input TemporalInput {
    validFrom: DateTime
    validTo: DateTime
}

type GraphStats {
    entityCount: Int!
    relationshipCount: Int!
    memoryUsageMB: Float!
}

scalar JSON
scalar DateTime
"""
