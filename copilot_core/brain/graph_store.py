"""Brain Graph Store — Neo4j/NetworkX backed knowledge graph persistence.

Implements Entity-Relation-Entity schema with temporal reasoning support.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None


class TemporalContext:
    """Temporal context for time-aware graph operations."""
    
    def __init__(self, valid_from: Optional[datetime] = None, 
                 valid_to: Optional[datetime] = None,
                 timestamp: Optional[datetime] = None):
        self.valid_from = valid_from or datetime.now()
        self.valid_to = valid_to
        self.timestamp = timestamp or datetime.now()
    
    def is_valid_at(self, query_time: datetime) -> bool:
        """Check if this context is valid at a given time."""
        if self.valid_to is None:
            return query_time >= self.valid_from
        return self.valid_from <= query_time <= self.valid_to
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TemporalContext:
        return cls(
            valid_from=datetime.fromisoformat(data["valid_from"]) if data.get("valid_from") else None,
            valid_to=datetime.fromisoformat(data["valid_to"]) if data.get("valid_to") else None,
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None
        )


class Entity:
    """Represents a node in the knowledge graph."""
    
    def __init__(self, entity_id: str, entity_type: str, 
                 name: Optional[str] = None, 
                 attributes: Optional[Dict[str, Any]] = None,
                 temporal: Optional[TemporalContext] = None):
        self.id = entity_id
        self.type = entity_type
        self.name = name or entity_id
        self.attributes = attributes or {}
        self.temporal = temporal or TemporalContext()
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "attributes": self.attributes,
            "temporal": self.temporal.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Entity:
        entity = cls(
            entity_id=data["id"],
            entity_type=data["type"],
            name=data.get("name"),
            attributes=data.get("attributes", {}),
            temporal=TemporalContext.from_dict(data["temporal"]) if data.get("temporal") else None
        )
        if data.get("created_at"):
            entity.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            entity.updated_at = datetime.fromisoformat(data["updated_at"])
        return entity


class Relationship:
    """Represents an edge in the knowledge graph."""
    
    def __init__(self, from_entity: str, relation_type: str, to_entity: str,
                 attributes: Optional[Dict[str, Any]] = None,
                 temporal: Optional[TemporalContext] = None):
        self.from_entity = from_entity
        self.type = relation_type
        self.to_entity = to_entity
        self.attributes = attributes or {}
        self.temporal = temporal or TemporalContext()
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_entity,
            "type": self.type,
            "to": self.to_entity,
            "attributes": self.attributes,
            "temporal": self.temporal.to_dict(),
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Relationship:
        rel = cls(
            from_entity=data["from"],
            relation_type=data["type"],
            to_entity=data["to"],
            attributes=data.get("attributes", {}),
            temporal=TemporalContext.from_dict(data["temporal"]) if data.get("temporal") else None
        )
        if data.get("created_at"):
            rel.created_at = datetime.fromisoformat(data["created_at"])
        return rel


class BrainGraphStore:
    """Knowledge graph store with Neo4j/NetworkX backend.
    
    Supports Entity-Relation-Entity schema with temporal reasoning.
    Falls back to in-memory NetworkX if Neo4j is unavailable.
    """
    
    def __init__(self, storage_path: Optional[str] = None,
                 neo4j_uri: Optional[str] = None,
                 neo4j_user: Optional[str] = None,
                 neo4j_password: Optional[str] = None,
                 auto_load: bool = True):
        self.storage_path = storage_path or "/tmp/brain_graph"
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []
        self._lock = threading.RLock()
        
        # Neo4j connection (optional)
        self.neo4j_driver = None
        if NEO4J_AVAILABLE and neo4j_uri:
            try:
                self.neo4j_driver = GraphDatabase.driver(
                    neo4j_uri, 
                    auth=(neo4j_user or "neo4j", neo4j_password or "")
                )
            except Exception:
                self.neo4j_driver = None
        
        # NetworkX graph (fallback or cache)
        if NETWORKX_AVAILABLE:
            self.graph = nx.MultiDiGraph()
        else:
            self.graph = None
        
        # Load from disk if exists (can be disabled for tests)
        if auto_load:
            self.load()
    
    def add_entity(self, entity_id: str, entity_data: Dict[str, Any]) -> bool:
        """Add or update an entity in the graph."""
        with self._lock:
            try:
                # Extract known fields, put everything else into attributes
                reserved_keys = {'id', 'type', 'name', 'attributes', 'temporal'}
                attributes = dict(entity_data.get("attributes", {}))
                
                # Merge any additional fields into attributes
                for key, value in entity_data.items():
                    if key not in reserved_keys:
                        attributes[key] = value
                
                entity = Entity(
                    entity_id=entity_id,
                    entity_type=entity_data.get("type", "unknown"),
                    name=entity_data.get("name"),
                    attributes=attributes,
                    temporal=TemporalContext() if "temporal" not in entity_data 
                             else TemporalContext.from_dict(entity_data["temporal"])
                )
                
                # Update if exists
                if entity_id in self.entities:
                    entity.created_at = self.entities[entity_id].created_at
                
                self.entities[entity_id] = entity
                
                # Add to NetworkX graph
                if self.graph is not None:
                    if self.graph.has_node(entity_id):
                        self.graph.nodes[entity_id].update(entity.to_dict())
                    else:
                        self.graph.add_node(entity_id, **entity.to_dict())
                
                # Sync to Neo4j if available
                if self.neo4j_driver:
                    self._sync_entity_to_neo4j(entity)
                
                return True
            except Exception as e:
                print(f"Error adding entity {entity_id}: {e}")
                return False
    
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an entity by ID."""
        with self._lock:
            entity = self.entities.get(entity_id)
            if entity:
                return entity.to_dict()
            
            # Try Neo4j if in-memory miss
            if self.neo4j_driver:
                return self._get_entity_from_neo4j(entity_id)
            
            return None
    
    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relationships."""
        with self._lock:
            if entity_id not in self.entities:
                return False
            
            # Remove relationships
            self.relationships = [
                r for r in self.relationships 
                if r.from_entity != entity_id and r.to_entity != entity_id
            ]
            
            # Remove from NetworkX
            if self.graph and self.graph.has_node(entity_id):
                self.graph.remove_node(entity_id)
            
            # Remove from Neo4j
            if self.neo4j_driver:
                self._delete_entity_from_neo4j(entity_id)
            
            del self.entities[entity_id]
            return True
    
    def add_relationship(self, from_entity: str, relation_type: str, 
                        to_entity: str, attributes: Optional[Dict[str, Any]] = None) -> bool:
        """Add a relationship between two entities."""
        with self._lock:
            # Verify entities exist
            if from_entity not in self.entities or to_entity not in self.entities:
                return False
            
            rel = Relationship(
                from_entity=from_entity,
                relation_type=relation_type,
                to_entity=to_entity,
                attributes=attributes or {}
            )
            
            self.relationships.append(rel)
            
            # Add to NetworkX - use relation_type as the key for MultiDiGraph
            if self.graph is not None:
                self.graph.add_edge(
                    from_entity, to_entity, 
                    key=relation_type,
                    type=relation_type,
                    attributes=rel.attributes,
                    temporal=rel.temporal.to_dict(),
                    created_at=rel.created_at.isoformat()
                )
            
            # Sync to Neo4j
            if self.neo4j_driver:
                self._sync_relationship_to_neo4j(rel)
            
            return True
    
    def get_relationships(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for an entity."""
        with self._lock:
            rels = [
                r.to_dict() for r in self.relationships 
                if r.from_entity == entity_id or r.to_entity == entity_id
            ]
            return rels
    
    def query_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """Query all entities of a specific type."""
        with self._lock:
            results = [
                e.to_dict() for e in self.entities.values() 
                if e.type == entity_type
            ]
            return results
    
    def traverse_from(self, entity_id: str, relation_type: str, 
                     max_depth: int = 1) -> List[Dict[str, Any]]:
        """Traverse graph from an entity following specific relations.
        
        Returns all entities reachable via the specified relation type within max_depth hops.
        """
        with self._lock:
            if self.graph is None or entity_id not in self.graph:
                return []
            
            connected = []
            visited = {entity_id}
            queue = [(entity_id, 0)]
            
            while queue:
                current, depth = queue.pop(0)
                if depth >= max_depth:
                    continue
                
                # Get all outgoing edges from current node
                if self.graph.has_node(current):
                    for neighbor in self.graph.successors(current):
                        if neighbor in visited:
                            continue
                        
                        # Check if there's an edge with matching relation type
                        if self.graph.has_edge(current, neighbor):
                            edge_data = self.graph.get_edge_data(current, neighbor)
                            # For MultiDiGraph, edge_data is {key: attrs}
                            found_match = False
                            if edge_data:
                                for key, data in edge_data.items():
                                    if data.get("type") == relation_type or key == relation_type:
                                        found_match = True
                                        break
                            
                            if found_match:
                                visited.add(neighbor)
                                neighbor_entity = self.entities.get(neighbor)
                                if neighbor_entity:
                                    connected.append(neighbor_entity.to_dict())
                                queue.append((neighbor, depth + 1))
            
            return connected
    
    def execute_sparql_like(self, query: str) -> List[Dict[str, Any]]:
        """Execute SPARQL-like query on the graph.
        
        Supports simplified patterns:
        - SELECT ?s ?p ?o WHERE { ?s ?p ?o }
        - SELECT ?e WHERE { ?e type "device" }
        - SELECT ?e WHERE { ?e connected_to ?x }
        """
        with self._lock:
            results = []
            query_lower = query.lower()
            
            # Simple pattern matching
            if "select" not in query_lower:
                return []
            
            # Extract variables
            import re
            var_pattern = r'\?(\w+)'
            variables = re.findall(var_pattern, query)
            
            # Handle type queries
            if 'type "' in query_lower or "type '" in query_lower:
                type_match = re.search(r'type ["\'](\w+)["\']', query, re.IGNORECASE)
                if type_match:
                    entity_type = type_match.group(1)
                    return self.query_by_type(entity_type)
            
            # Handle relationship queries
            if 'where {' in query_lower:
                where_clause = query_lower.split('where {')[1].split('}')[0]
                rel_match = re.search(r'\?(\w+)\s+(\w+)\s+\?(\w+)', where_clause)
                if rel_match:
                    subj_var, pred_var, obj_var = rel_match.groups()
                    
                    # Find matching relationships
                    for rel in self.relationships:
                        result = {}
                        if subj_var in variables:
                            result[subj_var] = rel.from_entity
                        if pred_var in variables:
                            result[pred_var] = rel.type
                        if obj_var in variables:
                            result[obj_var] = rel.to_entity
                        if result:
                            results.append(result)
            
            return results
    
    def save(self) -> bool:
        """Persist graph to disk."""
        with self._lock:
            try:
                path = Path(self.storage_path)
                path.mkdir(parents=True, exist_ok=True)
                
                # Save entities
                entities_file = path / "entities.json"
                with open(entities_file, 'w') as f:
                    json.dump({k: v.to_dict() for k, v in self.entities.items()}, f, indent=2)
                
                # Save relationships
                rels_file = path / "relationships.json"
                with open(rels_file, 'w') as f:
                    json.dump([r.to_dict() for r in self.relationships], f, indent=2)
                
                # Save NetworkX graph if available
                if self.graph and NETWORKX_AVAILABLE:
                    graph_file = path / "graph.graphml"
                    nx.write_graphml(self.graph, graph_file)
                
                return True
            except Exception as e:
                print(f"Error saving graph: {e}")
                return False
    
    def load(self) -> bool:
        """Load graph from disk."""
        with self._lock:
            try:
                path = Path(self.storage_path)
                if not path.exists():
                    return True  # No existing data
                
                # Load entities
                entities_file = path / "entities.json"
                if entities_file.exists():
                    with open(entities_file, 'r') as f:
                        data = json.load(f)
                        self.entities = {k: Entity.from_dict(v) for k, v in data.items()}
                
                # Load relationships
                rels_file = path / "relationships.json"
                if rels_file.exists():
                    with open(rels_file, 'r') as f:
                        data = json.load(f)
                        self.relationships = [Relationship.from_dict(r) for r in data]
                
                # Load NetworkX graph
                graph_file = path / "graph.graphml"
                if graph_file.exists() and NETWORKX_AVAILABLE:
                    self.graph = nx.read_graphml(graph_file)
                
                return True
            except Exception as e:
                print(f"Error loading graph: {e}")
                return False
    
    def clear(self) -> None:
        """Clear all graph data."""
        with self._lock:
            self.entities.clear()
            self.relationships.clear()
            if self.graph:
                self.graph.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        with self._lock:
            stats = {
                "entity_count": len(self.entities),
                "relationship_count": len(self.relationships),
                "memory_usage_mb": 0
            }
            
            # Estimate memory usage
            import sys
            entity_mem = sum(sys.getsizeof(e.to_dict()) for e in self.entities.values())
            rel_mem = sum(sys.getsizeof(r.to_dict()) for r in self.relationships)
            stats["memory_usage_mb"] = (entity_mem + rel_mem) / (1024 * 1024)
            
            if self.graph and NETWORKX_AVAILABLE:
                stats["graph_nodes"] = self.graph.number_of_nodes()
                stats["graph_edges"] = self.graph.number_of_edges()
            
            return stats
    
    def export_to_json(self) -> Dict[str, Any]:
        """Export entire graph to JSON.
        
        Returns dict where entity IDs are top-level keys for direct lookup.
        Also includes _relationships and _exported_at metadata.
        """
        with self._lock:
            # Start with entity dict (entity_id -> entity_data)
            result = {k: v.to_dict() for k, v in self.entities.items()}
            # Add relationships array
            result["_relationships"] = [r.to_dict() for r in self.relationships]
            result["_exported_at"] = datetime.now().isoformat()
            return result
    
    def export_to_graphml(self) -> str:
        """Export graph to GraphML format.
        
        Note: GraphML has limited type support. Complex nested dicts in attributes
        will be serialized as JSON strings.
        """
        with self._lock:
            if not self.graph or not NETWORKX_AVAILABLE:
                return ""
            
            try:
                import io
                import json as json_module
                
                def clean_value(val):
                    """Convert any value to a GraphML-compatible type."""
                    if val is None:
                        return None
                    elif isinstance(val, bool):
                        return val
                    elif isinstance(val, (int, float)):
                        return val
                    elif isinstance(val, str):
                        return val
                    elif isinstance(val, dict):
                        # Stringify all dicts to avoid type issues
                        return json_module.dumps(val)
                    elif isinstance(val, (list, tuple)):
                        return json_module.dumps(val)
                    else:
                        return str(val)
                
                # Create a new graph with cleaned attributes
                export_graph = nx.MultiDiGraph()
                
                # Copy nodes with cleaned attributes
                for node in self.graph.nodes():
                    node_data = dict(self.graph.nodes[node])
                    cleaned_data = {}
                    for key, value in node_data.items():
                        cleaned_data[key] = clean_value(value)
                    export_graph.add_node(node, **cleaned_data)
                
                # Copy edges with cleaned attributes
                for u, v, key, data in self.graph.edges(keys=True, data=True):
                    cleaned_data = {}
                    for k, val in data.items():
                        cleaned_data[k] = clean_value(val)
                    export_graph.add_edge(u, v, key=key, **cleaned_data)
                
                buffer = io.BytesIO()
                nx.write_graphml(export_graph, buffer)
                return buffer.getvalue().decode('utf-8')
            except Exception as e:
                print(f"Error exporting to GraphML: {e}")
                import traceback
                traceback.print_exc()
                return ""
    
    # Neo4j sync methods
    def _sync_entity_to_neo4j(self, entity: Entity) -> None:
        """Sync entity to Neo4j database."""
        if not self.neo4j_driver:
            return
        
        with self.neo4j_driver.session() as session:
            session.run("""
                MERGE (e:Entity {id: $id})
                SET e.type = $type,
                    e.name = $name,
                    e.attributes = $attributes,
                    e.temporal = $temporal,
                    e.updated_at = datetime()
            """, {
                "id": entity.id,
                "type": entity.type,
                "name": entity.name,
                "attributes": entity.attributes,
                "temporal": entity.temporal.to_dict()
            })
    
    def _get_entity_from_neo4j(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve entity from Neo4j."""
        if not self.neo4j_driver:
            return None
        
        with self.neo4j_driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {id: $id})
                RETURN e
            """, {"id": entity_id})
            
            record = result.single()
            if record:
                node = record["e"]
                return dict(node)
            return None
    
    def _delete_entity_from_neo4j(self, entity_id: str) -> None:
        """Delete entity from Neo4j."""
        if not self.neo4j_driver:
            return
        
        with self.neo4j_driver.session() as session:
            session.run("""
                MATCH (e:Entity {id: $id})
                DETACH DELETE e
            """, {"id": entity_id})
    
    def _sync_relationship_to_neo4j(self, rel: Relationship) -> None:
        """Sync relationship to Neo4j."""
        if not self.neo4j_driver:
            return
        
        with self.neo4j_driver.session() as session:
            session.run("""
                MATCH (a:Entity {id: $from}), (b:Entity {id: $to})
                MERGE (a)-[r:RELATIONSHIP {type: $type}]->(b)
                SET r.attributes = $attributes,
                    r.temporal = $temporal
            """, {
                "from": rel.from_entity,
                "to": rel.to_entity,
                "type": rel.type,
                "attributes": rel.attributes,
                "temporal": rel.temporal.to_dict()
            })
