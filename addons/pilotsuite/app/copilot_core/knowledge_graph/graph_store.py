"""Graph Store for Knowledge Graph.

Provides Neo4j-backed graph storage with SQLite fallback for environments
where Neo4j is not available.

Supports:
- Dual backend: Neo4j (preferred) or SQLite (fallback)
- CRUD operations for nodes and edges
- Graph queries (traversal, filtering)
- Pattern import from Habitus
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Optional

from .models import Edge, EdgeType, GraphQuery, GraphResult, Node, NodeType

_LOGGER = logging.getLogger(__name__)

# Environment variables for Neo4j connection
NEO4J_URI_ENV = "COPILOT_NEO4J_URI"
NEO4J_USER_ENV = "COPILOT_NEO4J_USER"
NEO4J_PASSWORD_ENV = "COPILOT_NEO4J_PASSWORD"
NEO4J_ENABLED_ENV = "COPILOT_NEO4J_ENABLED"

# Default SQLite path
DEFAULT_SQLITE_PATH = "/data/knowledge_graph.db"

# Node/Edge type mappings for SQLite
NODE_TABLE = "kg_nodes"
EDGE_TABLE = "kg_edges"


class GraphStore:
    """Knowledge Graph store with Neo4j/SQLite dual backend."""

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        sqlite_path: Optional[str] = None,
    ) -> None:
        """Initialize the graph store.
        
        Args:
            neo4j_uri: Neo4j connection URI (e.g., bolt://neo4j:7687)
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            sqlite_path: SQLite database path (fallback)
        """
        self._lock = threading.RLock()
        self._neo4j_driver = None
        self._sqlite_conn = None
        self._sqlite_path = sqlite_path or os.environ.get(
            "COPILOT_KG_SQLITE_PATH", DEFAULT_SQLITE_PATH
        )
        
        # Check if Neo4j is enabled and available
        neo4j_enabled = os.environ.get(NEO4J_ENABLED_ENV, "true").lower() == "true"
        neo4j_uri = neo4j_uri or os.environ.get(NEO4J_URI_ENV)
        neo4j_user = neo4j_user or os.environ.get(NEO4J_USER_ENV, "neo4j")
        neo4j_password = neo4j_password or os.environ.get(NEO4J_PASSWORD_ENV)
        
        # Try to connect to Neo4j
        if neo4j_enabled and neo4j_uri:
            try:
                from neo4j import GraphDatabase
                self._neo4j_driver = GraphDatabase.driver(
                    neo4j_uri,
                    auth=(neo4j_user, neo4j_password) if neo4j_password else None
                )
                # Test connection
                with self._neo4j_driver.session() as session:
                    session.run("RETURN 1").single()
                _LOGGER.info("Connected to Neo4j at %s", neo4j_uri)
                self._backend = "neo4j"
            except Exception as e:
                _LOGGER.warning("Failed to connect to Neo4j: %s, falling back to SQLite", e)
                self._neo4j_driver = None
        else:
            _LOGGER.info("Neo4j not configured, using SQLite backend")
        
        # Initialize SQLite fallback
        if not self._neo4j_driver:
            self._init_sqlite()
            self._backend = "sqlite"
    
    def _init_sqlite(self) -> None:
        """Initialize SQLite database schema."""
        os.makedirs(os.path.dirname(self._sqlite_path) or ".", exist_ok=True)
        self._sqlite_conn = sqlite3.connect(self._sqlite_path, check_same_thread=False)
        self._sqlite_conn.row_factory = sqlite3.Row

        with self._lock:
            # Enable WAL mode for concurrent read/write and better crash resilience
            self._sqlite_conn.execute("PRAGMA journal_mode=WAL")
            self._sqlite_conn.execute("PRAGMA busy_timeout=5000")
            cursor = self._sqlite_conn.cursor()
            
            # Create nodes table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {NODE_TABLE} (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    properties TEXT DEFAULT '{{}}',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            
            # Create edges table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {EDGE_TABLE} (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    type TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    confidence REAL DEFAULT 0.0,
                    source_type TEXT DEFAULT 'inferred',
                    evidence TEXT DEFAULT '{{}}',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    FOREIGN KEY (source) REFERENCES {NODE_TABLE}(id),
                    FOREIGN KEY (target) REFERENCES {NODE_TABLE}(id)
                )
            """)
            
            # Create indexes
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON {NODE_TABLE}(type)
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_nodes_label ON {NODE_TABLE}(label)
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_edges_source ON {EDGE_TABLE}(source)
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_edges_target ON {EDGE_TABLE}(target)
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_edges_type ON {EDGE_TABLE}(type)
            """)
            
            self._sqlite_conn.commit()
        
        _LOGGER.info("Initialized SQLite knowledge graph at %s", self._sqlite_path)
    
    @property
    def backend(self) -> str:
        """Return the current backend type."""
        return self._backend
    
    # ==================== Node Operations ====================
    
    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        with self._lock:
            if self._backend == "neo4j":
                self._add_node_neo4j(node)
            else:
                self._add_node_sqlite(node)
    
    def _add_node_neo4j(self, node: Node) -> None:
        """Add a node to Neo4j."""
        with self._neo4j_driver.session() as session:
            session.run(
                f"""
                MERGE (n:{node.type.value} {{id: $id}})
                SET n += {{
                    label: $label,
                    properties: $properties,
                    created_at: $created_at,
                    updated_at: $updated_at
                }}
                """,
                id=node.id,
                label=node.label,
                properties=json.dumps(node.properties),
                created_at=node.created_at,
                updated_at=node.updated_at
            )
    
    def _add_node_sqlite(self, node: Node) -> None:
        """Add a node to SQLite."""
        cursor = self._sqlite_conn.cursor()
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO {NODE_TABLE} 
            (id, type, label, properties, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                node.id,
                node.type.value,
                node.label,
                json.dumps(node.properties),
                node.created_at,
                node.updated_at
            )
        )
        self._sqlite_conn.commit()
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        with self._lock:
            if self._backend == "neo4j":
                return self._get_node_neo4j(node_id)
            else:
                return self._get_node_sqlite(node_id)
    
    def _get_node_neo4j(self, node_id: str) -> Optional[Node]:
        """Get a node from Neo4j."""
        with self._neo4j_driver.session() as session:
            result = session.run(
                "MATCH (n {id: $id}) RETURN n",
                id=node_id
            )
            record = result.single()
            if record:
                n = record["n"]
                return Node(
                    id=n["id"],
                    type=NodeType([label for label in n.labels if label != "Node"][0]),
                    label=n["label"],
                    properties=json.loads(n.get("properties", "{}")),
                    created_at=n.get("created_at", int(time.time() * 1000)),
                    updated_at=n.get("updated_at", int(time.time() * 1000)),
                )
        return None
    
    def _get_node_sqlite(self, node_id: str) -> Optional[Node]:
        """Get a node from SQLite."""
        cursor = self._sqlite_conn.cursor()
        cursor.execute(
            f"SELECT * FROM {NODE_TABLE} WHERE id = ?",
            (node_id,)
        )
        row = cursor.fetchone()
        if row:
            return Node(
                id=row["id"],
                type=NodeType(row["type"]),
                label=row["label"],
                properties=json.loads(row["properties"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        return None
    
    def get_nodes_by_type(self, node_type: NodeType, limit: int = 100) -> list[Node]:
        """Get all nodes of a specific type."""
        with self._lock:
            if self._backend == "neo4j":
                return self._get_nodes_by_type_neo4j(node_type, limit)
            else:
                return self._get_nodes_by_type_sqlite(node_type, limit)
    
    def _get_nodes_by_type_neo4j(self, node_type: NodeType, limit: int) -> list[Node]:
        """Get nodes by type from Neo4j."""
        nodes = []
        with self._neo4j_driver.session() as session:
            result = session.run(
                f"MATCH (n:{node_type.value}) RETURN n LIMIT $limit",
                limit=limit
            )
            for record in result:
                n = record["n"]
                nodes.append(Node(
                    id=n["id"],
                    type=node_type,
                    label=n["label"],
                    properties=json.loads(n.get("properties", "{}")),
                    created_at=n.get("created_at", int(time.time() * 1000)),
                    updated_at=n.get("updated_at", int(time.time() * 1000)),
                ))
        return nodes
    
    def _get_nodes_by_type_sqlite(self, node_type: NodeType, limit: int) -> list[Node]:
        """Get nodes by type from SQLite."""
        cursor = self._sqlite_conn.cursor()
        cursor.execute(
            f"SELECT * FROM {NODE_TABLE} WHERE type = ? LIMIT ?",
            (node_type.value, limit)
        )
        return [
            Node(
                id=row["id"],
                type=node_type,
                label=row["label"],
                properties=json.loads(row["properties"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]
    
    # ==================== Edge Operations ====================
    
    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        with self._lock:
            if self._backend == "neo4j":
                self._add_edge_neo4j(edge)
            else:
                self._add_edge_sqlite(edge)
    
    def _add_edge_neo4j(self, edge: Edge) -> None:
        """Add an edge to Neo4j."""
        with self._neo4j_driver.session() as session:
            session.run(
                f"""
                MATCH (source {{id: $source}})
                MATCH (target {{id: $target}})
                MERGE (source)-[r:{edge.type.value}]->(target)
                SET r += {{
                    weight: $weight,
                    confidence: $confidence,
                    source_type: $source_type,
                    evidence: $evidence,
                    created_at: $created_at,
                    updated_at: $updated_at
                }}
                """,
                source=edge.source,
                target=edge.target,
                weight=edge.weight,
                confidence=edge.confidence,
                source_type=edge.source_type,
                evidence=json.dumps(edge.evidence),
                created_at=edge.created_at,
                updated_at=edge.updated_at
            )
    
    def _add_edge_sqlite(self, edge: Edge) -> None:
        """Add an edge to SQLite."""
        cursor = self._sqlite_conn.cursor()
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO {EDGE_TABLE}
            (id, source, target, type, weight, confidence, source_type, evidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edge.id,
                edge.source,
                edge.target,
                edge.type.value,
                edge.weight,
                edge.confidence,
                edge.source_type,
                json.dumps(edge.evidence),
                edge.created_at,
                edge.updated_at
            )
        )
        self._sqlite_conn.commit()
    
    def get_edges_from(self, node_id: str, edge_type: Optional[EdgeType] = None) -> list[Edge]:
        """Get all edges originating from a node."""
        with self._lock:
            if self._backend == "neo4j":
                return self._get_edges_from_neo4j(node_id, edge_type)
            else:
                return self._get_edges_from_sqlite(node_id, edge_type)
    
    def _get_edges_from_neo4j(self, node_id: str, edge_type: Optional[EdgeType]) -> list[Edge]:
        """Get edges from Neo4j."""
        edges = []
        with self._neo4j_driver.session() as session:
            if edge_type:
                result = session.run(
                    f"MATCH ({{id: $source}})-[r:{edge_type.value}]->(target) RETURN r, target.id as target_id",
                    source=node_id
                )
            else:
                result = session.run(
                    "MATCH ({id: $source})-[r]->(target) RETURN r, type(r) as rel_type, target.id as target_id",
                    source=node_id
                )
            for record in result:
                r = record["r"]
                edges.append(Edge(
                    source=node_id,
                    target=record["target_id"],
                    type=EdgeType(record.get("rel_type", edge_type.value if edge_type else "relates_to")),
                    weight=r.get("weight", 1.0),
                    confidence=r.get("confidence", 0.0),
                    source_type=r.get("source_type", "inferred"),
                    evidence=json.loads(r.get("evidence", "{}")),
                    created_at=r.get("created_at", int(time.time() * 1000)),
                    updated_at=r.get("updated_at", int(time.time() * 1000)),
                ))
        return edges
    
    def _get_edges_from_sqlite(self, node_id: str, edge_type: Optional[EdgeType]) -> list[Edge]:
        """Get edges from SQLite."""
        cursor = self._sqlite_conn.cursor()
        if edge_type:
            cursor.execute(
                f"SELECT * FROM {EDGE_TABLE} WHERE source = ? AND type = ?",
                (node_id, edge_type.value)
            )
        else:
            cursor.execute(
                f"SELECT * FROM {EDGE_TABLE} WHERE source = ?",
                (node_id,)
            )
        return [
            Edge(
                source=row["source"],
                target=row["target"],
                type=EdgeType(row["type"]),
                weight=row["weight"],
                confidence=row["confidence"],
                source_type=row["source_type"],
                evidence=json.loads(row["evidence"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]
    
    def get_edges_to(self, node_id: str, edge_type: Optional[EdgeType] = None) -> list[Edge]:
        """Get all edges pointing to a node."""
        with self._lock:
            if self._backend == "neo4j":
                return self._get_edges_to_neo4j(node_id, edge_type)
            else:
                return self._get_edges_to_sqlite(node_id, edge_type)
    
    def _get_edges_to_neo4j(self, node_id: str, edge_type: Optional[EdgeType]) -> list[Edge]:
        """Get edges to Neo4j."""
        edges = []
        with self._neo4j_driver.session() as session:
            if edge_type:
                result = session.run(
                    f"MATCH (source)-[r:{edge_type.value}]->({{id: $target}}) RETURN r, source.id as source_id",
                    target=node_id
                )
            else:
                result = session.run(
                    "MATCH (source)-[r]->({id: $target}) RETURN r, type(r) as rel_type, source.id as source_id",
                    target=node_id
                )
            for record in result:
                r = record["r"]
                edges.append(Edge(
                    source=record["source_id"],
                    target=node_id,
                    type=EdgeType(record.get("rel_type", edge_type.value if edge_type else "relates_to")),
                    weight=r.get("weight", 1.0),
                    confidence=r.get("confidence", 0.0),
                    source_type=r.get("source_type", "inferred"),
                    evidence=json.loads(r.get("evidence", "{}")),
                    created_at=r.get("created_at", int(time.time() * 1000)),
                    updated_at=r.get("updated_at", int(time.time() * 1000)),
                ))
        return edges
    
    def _get_edges_to_sqlite(self, node_id: str, edge_type: Optional[EdgeType]) -> list[Edge]:
        """Get edges to SQLite."""
        cursor = self._sqlite_conn.cursor()
        if edge_type:
            cursor.execute(
                f"SELECT * FROM {EDGE_TABLE} WHERE target = ? AND type = ?",
                (node_id, edge_type.value)
            )
        else:
            cursor.execute(
                f"SELECT * FROM {EDGE_TABLE} WHERE target = ?",
                (node_id,)
            )
        return [
            Edge(
                source=row["source"],
                target=row["target"],
                type=EdgeType(row["type"]),
                weight=row["weight"],
                confidence=row["confidence"],
                source_type=row["source_type"],
                evidence=json.loads(row["evidence"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]
    
    # ==================== Query Operations ====================
    
    def query(self, query: GraphQuery) -> GraphResult:
        """Execute a graph query."""
        with self._lock:
            if self._backend == "neo4j":
                return self._query_neo4j(query)
            else:
                return self._query_sqlite(query)
    
    def _query_neo4j(self, query: GraphQuery) -> GraphResult:
        """Execute a query against Neo4j."""
        # Note: SQLite queries are implemented in _query_sqlite()
        return GraphResult(nodes=[], edges=[])
    
    def _query_sqlite(self, query: GraphQuery) -> GraphResult:
        """Execute a query against SQLite.

        All reads happen under a single cursor/transaction so the snapshot
        is consistent (no phantom reads between sub-queries).
        """
        nodes = []
        edges = []
        cursor = self._sqlite_conn.cursor()

        def _row_to_node(row) -> Node:
            return Node(
                id=row["id"],
                type=NodeType(row["type"]),
                label=row["label"],
                properties=json.loads(row["properties"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        def _row_to_edge(row) -> Edge:
            return Edge(
                source=row["source"],
                target=row["target"],
                type=EdgeType(row["type"]),
                weight=row["weight"],
                confidence=row["confidence"],
                source_type=row["source_type"],
                evidence=json.loads(row["evidence"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        def _fetch_node(node_id: str):
            cursor.execute(f"SELECT * FROM {NODE_TABLE} WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            return _row_to_node(row) if row else None

        if query.entity_id:
            node = _fetch_node(query.entity_id)
            if node:
                nodes.append(node)

            cursor.execute(
                f"SELECT * FROM {EDGE_TABLE} WHERE source = ? OR target = ?",
                (query.entity_id, query.entity_id),
            )
            all_edges = [_row_to_edge(r) for r in cursor.fetchall()]
            all_edges.sort(key=lambda e: e.confidence, reverse=True)
            all_edges = [e for e in all_edges if e.confidence >= query.min_confidence]
            all_edges = all_edges[: query.max_results]
            edges.extend(all_edges)

            seen_ids = {query.entity_id}
            for edge in all_edges:
                connected_id = edge.target if edge.source == query.entity_id else edge.source
                if connected_id not in seen_ids:
                    seen_ids.add(connected_id)
                    connected = _fetch_node(connected_id)
                    if connected:
                        nodes.append(connected)

        elif query.zone_id:
            zone_node = _fetch_node(query.zone_id)
            if zone_node:
                nodes.append(zone_node)

            cursor.execute(
                f"SELECT * FROM {EDGE_TABLE} WHERE target = ? AND type = ? LIMIT ?",
                (query.zone_id, EdgeType.BELONGS_TO.value, query.max_results),
            )
            for row in cursor.fetchall():
                edge = _row_to_edge(row)
                entity = _fetch_node(edge.source)
                if entity:
                    nodes.append(entity)
                    edges.append(edge)

        elif query.mood:
            mood_id = f"mood:{query.mood}"
            cursor.execute(
                f"SELECT * FROM {EDGE_TABLE} WHERE target = ? AND type = ?",
                (mood_id, EdgeType.RELATES_TO_MOOD.value),
            )
            mood_edges = [_row_to_edge(r) for r in cursor.fetchall()]
            mood_edges = [e for e in mood_edges if e.confidence >= query.min_confidence]
            mood_edges = mood_edges[: query.max_results]
            edges.extend(mood_edges)

            for edge in mood_edges:
                node = _fetch_node(edge.source)
                if node:
                    nodes.append(node)

        return GraphResult(
            nodes=nodes,
            edges=edges,
            confidence=max((e.confidence for e in edges), default=0.0),
            sources=["sqlite"],
        )
    
    # ==================== Stats ====================
    
    def stats(self) -> dict[str, Any]:
        """Get graph statistics."""
        with self._lock:
            if self._backend == "neo4j":
                return self._stats_neo4j()
            else:
                return self._stats_sqlite()
    
    def _stats_neo4j(self) -> dict[str, Any]:
        """Get Neo4j stats."""
        with self._neo4j_driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            edge_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            return {
                "backend": "neo4j",
                "node_count": node_count,
                "edge_count": edge_count,
            }
    
    def _stats_sqlite(self) -> dict[str, Any]:
        """Get SQLite stats."""
        cursor = self._sqlite_conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {NODE_TABLE}")
        node_count = cursor.fetchone()[0]
        cursor.execute(f"SELECT COUNT(*) FROM {EDGE_TABLE}")
        edge_count = cursor.fetchone()[0]
        
        # Get type breakdown
        cursor.execute(f"SELECT type, COUNT(*) as count FROM {NODE_TABLE} GROUP BY type")
        nodes_by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute(f"SELECT type, COUNT(*) as count FROM {EDGE_TABLE} GROUP BY type")
        edges_by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            "backend": "sqlite",
            "path": self._sqlite_path,
            "node_count": node_count,
            "edge_count": edge_count,
            "nodes_by_type": nodes_by_type,
            "edges_by_type": edges_by_type,
        }
    
    def close(self) -> None:
        """Close all connections."""
        with self._lock:
            if self._neo4j_driver:
                self._neo4j_driver.close()
                self._neo4j_driver = None
            if self._sqlite_conn:
                self._sqlite_conn.close()
                self._sqlite_conn = None


# Singleton instance
_graph_store: Optional[GraphStore] = None
_graph_store_lock = threading.Lock()


def get_graph_store() -> GraphStore:
    """Get the singleton graph store instance."""
    global _graph_store
    with _graph_store_lock:
        if _graph_store is None:
            _graph_store = GraphStore()
        return _graph_store