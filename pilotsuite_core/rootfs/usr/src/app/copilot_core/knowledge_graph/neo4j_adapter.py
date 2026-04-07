"""
Neo4j Adapter for PilotSuite Knowledge Graph.

Provides a dedicated adapter layer for Neo4j operations, including:
- Brain Graph export to Neo4j format
- Cypher query builder and executor
- Visualization data export
- Batch operations for efficient bulk writes
- Connection pooling and error handling

This adapter works alongside the existing GraphStore but provides
more advanced Neo4j-specific features like:
- Complex Cypher query construction
- Graph algorithms integration
- Transaction management
- Schema constraints and indexes
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from .models import Edge, EdgeType, Node, NodeType

_LOGGER = logging.getLogger(__name__)

# Default configuration
DEFAULT_NEO4J_URI = os.environ.get("COPILOT_NEO4J_URI", "bolt://localhost:7687")
DEFAULT_NEO4J_USER = os.environ.get("COPILOT_NEO4J_USER", "neo4j")
DEFAULT_NEO4J_PASSWORD = os.environ.get("COPILOT_NEO4J_PASSWORD", "")
DEFAULT_NEO4J_DATABASE = os.environ.get("COPILOT_NEO4J_DATABASE", "neo4j")
DEFAULT_NEO4J_TIMEOUT = int(os.environ.get("COPILOT_NEO4J_TIMEOUT", "30"))
DEFAULT_NEO4J_MAX_CONNECTION_POOL_SIZE = int(
    os.environ.get("COPILOT_NEO4J_MAX_POOL_SIZE", "50")
)


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""

    uri: str = DEFAULT_NEO4J_URI
    user: str = DEFAULT_NEO4J_USER
    password: str = DEFAULT_NEO4J_PASSWORD
    database: str = DEFAULT_NEO4J_DATABASE
    timeout: int = DEFAULT_NEO4J_TIMEOUT
    max_pool_size: int = DEFAULT_NEO4J_MAX_CONNECTION_POOL_SIZE
    encrypted: bool = False
    trusted_certificates: bool = True


@dataclass
class CypherQuery:
    """Represents a Cypher query with parameters."""

    query: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    read_only: bool = True
    description: str = ""


@dataclass
class QueryResult:
    """Result of a Cypher query execution."""

    records: List[Dict[str, Any]]
    summary: Dict[str, Any]
    query: str
    execution_time_ms: float
    success: bool = True
    error: Optional[str] = None


class Neo4jAdapter:
    """
    Dedicated adapter for Neo4j operations.

    Provides advanced Neo4j features beyond basic CRUD:
    - Complex Cypher query construction
    - Batch operations
    - Graph algorithms
    - Schema management
    - Visualization data export
    """

    def __init__(self, config: Optional[Neo4jConfig] = None):
        """
        Initialize the Neo4j adapter.

        Args:
            config: Neo4j configuration. Uses environment variables if not provided.
        """
        self.config = config or Neo4jConfig()
        self._driver = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to Neo4j.

        Returns:
            True if connection successful, False otherwise.
        """
        if self._connected and self._driver:
            return True

        try:
            from neo4j import GraphDatabase
            from neo4j.exceptions import ServiceUnavailable, AuthError

            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password)
                if self.config.password
                else None,
                max_connection_pool_size=self.config.max_pool_size,
                connection_acquisition_timeout=self.config.timeout,
                encrypted=self.config.encrypted,
            )

            # Verify connectivity
            self._driver.verify_connectivity()
            self._connected = True
            _LOGGER.info(
                "Connected to Neo4j at %s (database: %s)",
                self.config.uri,
                self.config.database,
            )
            return True

        except ServiceUnavailable as e:
            _LOGGER.error("Neo4j service unavailable: %s", e)
            self._connected = False
            return False
        except AuthError as e:
            _LOGGER.error("Neo4j authentication failed: %s", e)
            self._connected = False
            return False
        except Exception as e:
            _LOGGER.error("Failed to connect to Neo4j: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close the Neo4j connection."""
        if self._driver:
            try:
                self._driver.close()
                _LOGGER.info("Disconnected from Neo4j")
            except Exception as e:
                _LOGGER.warning("Error closing Neo4j connection: %s", e)
            finally:
                self._driver = None
                self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if adapter is connected to Neo4j."""
        return self._connected and self._driver is not None

    @contextmanager
    def session(
        self, database: Optional[str] = None
    ) -> Generator[Any, None, None]:
        """
        Context manager for Neo4j sessions.

        Args:
            database: Optional database name (uses config default if not provided).

        Yields:
            Neo4j session object.

        Example:
            with adapter.session() as session:
                result = session.run("MATCH (n) RETURN n LIMIT 10")
        """
        if not self._connected:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")

        session = None
        try:
            session = self._driver.session(
                database=database or self.config.database
            )
            yield session
        finally:
            if session:
                session.close()

    @contextmanager
    def transaction(
        self, database: Optional[str] = None
    ) -> Generator[Any, None, None]:
        """
        Context manager for Neo4j transactions.

        Args:
            database: Optional database name.

        Yields:
            Neo4j transaction object.

        Example:
            with adapter.transaction() as tx:
                tx.run("CREATE (n:Node {id: $id})", id="test")
                # Transaction auto-commits on exit
        """
        if not self._connected:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")

        tx = None
        try:
            with self.session(database) as session:
                tx = session.begin_transaction()
                yield tx
                tx.commit()
        except Exception as e:
            if tx:
                tx.rollback()
                _LOGGER.warning("Transaction rolled back: %s", e)
            raise

    # ==================== Schema Management ====================

    def create_constraints(self) -> QueryResult:
        """
        Create uniqueness constraints for node IDs.

        Returns:
            QueryResult with execution summary.
        """
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Zone) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Area) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Service) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Mood) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Pattern) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Context) REQUIRE n.id IS UNIQUE",
        ]

        return self._execute_batch(constraints, description="Create uniqueness constraints")

    def create_indexes(self) -> QueryResult:
        """
        Create indexes for common query patterns.

        Returns:
            QueryResult with execution summary.
        """
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.label)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.domain)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.area_id)",
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:TRIGGERS]-() ON (r.confidence)",
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:BELONGS_TO]-() ON (r.weight)",
            "CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATES_TO_MOOD]-() ON (r.confidence)",
        ]

        return self._execute_batch(indexes, description="Create indexes")

    def ensure_schema(self) -> Dict[str, Any]:
        """
        Ensure all constraints and indexes exist.

        Returns:
            Dictionary with schema status.
        """
        result = {
            "constraints": False,
            "indexes": False,
            "success": False,
        }

        try:
            constraints_result = self.create_constraints()
            result["constraints"] = constraints_result.success

            indexes_result = self.create_indexes()
            result["indexes"] = indexes_result.success

            result["success"] = result["constraints"] and result["indexes"]
        except Exception as e:
            result["error"] = str(e)
            _LOGGER.error("Error ensuring schema: %s", e)

        return result

    # ==================== Brain Graph Export ====================

    def export_brain_graph(
        self,
        nodes: List[Node],
        edges: List[Edge],
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Export Brain Graph data to Neo4j.

        Args:
            nodes: List of nodes to export.
            edges: List of edges to export.
            batch_size: Number of items to process per batch.

        Returns:
            Dictionary with export statistics.
        """
        if not self._connected:
            raise RuntimeError("Not connected to Neo4j")

        stats = {
            "nodes_imported": 0,
            "edges_imported": 0,
            "batches": 0,
            "errors": [],
            "execution_time_ms": 0,
        }

        start_time = time.time()

        try:
            # Export nodes in batches
            with self.transaction() as tx:
                for i in range(0, len(nodes), batch_size):
                    batch = nodes[i : i + batch_size]
                    self._import_node_batch(tx, batch)
                    stats["nodes_imported"] += len(batch)
                    stats["batches"] += 1

            # Export edges in batches
            with self.transaction() as tx:
                for i in range(0, len(edges), batch_size):
                    batch = edges[i : i + batch_size]
                    self._import_edge_batch(tx, batch)
                    stats["edges_imported"] += len(batch)
                    stats["batches"] += 1

        except Exception as e:
            stats["errors"].append(str(e))
            _LOGGER.error("Error exporting brain graph: %s", e)

        stats["execution_time_ms"] = (time.time() - start_time) * 1000
        return stats

    def _import_node_batch(
        self, tx: Any, nodes: List[Node]
    ) -> None:
        """Import a batch of nodes in a single transaction."""
        for node in nodes:
            # Map node type to Neo4j label
            label = self._get_neo4j_label(node.type)

            tx.run(
                f"""
                MERGE (n:{label} {{id: $id}})
                SET n += {{
                    label: $label,
                    type: $type,
                    properties: $properties,
                    created_at: $created_at,
                    updated_at: $updated_at
                }}
                """,
                id=node.id,
                label=node.label,
                type=node.type.value,
                properties=json.dumps(node.properties),
                created_at=node.created_at,
                updated_at=node.updated_at,
            )

    def _import_edge_batch(
        self, tx: Any, edges: List[Edge]
    ) -> None:
        """Import a batch of edges in a single transaction."""
        for edge in edges:
            # Get relationship type
            rel_type = edge.type.value.upper()

            tx.run(
                f"""
                MATCH (source {{id: $source}})
                MATCH (target {{id: $target}})
                MERGE (source)-[r:{rel_type}]->(target)
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
                updated_at=edge.updated_at,
            )

    def _get_neo4j_label(self, node_type: NodeType) -> str:
        """Map NodeType to Neo4j label."""
        label_map = {
            NodeType.ENTITY: "Entity",
            NodeType.ZONE: "Zone",
            NodeType.AREA: "Area",
            NodeType.SERVICE: "Service",
            NodeType.MOOD: "Mood",
            NodeType.PATTERN: "Pattern",
            NodeType.CONTEXT: "Context",
            NodeType.ACTION: "Action",
            NodeType.STATE: "State",
        }
        return label_map.get(node_type, "Node")

    # ==================== Cypher Query Adapter ====================

    def execute(self, cypher: Union[str, CypherQuery]) -> QueryResult:
        """
        Execute a Cypher query.

        Args:
            cypher: Cypher query string or CypherQuery object.

        Returns:
            QueryResult with records and metadata.
        """
        if isinstance(cypher, CypherQuery):
            query_str = cypher.query
            params = cypher.parameters
            read_only = cypher.read_only
            description = cypher.description
        else:
            query_str = cypher
            params = {}
            read_only = self._is_read_only_query(cypher)
            description = ""

        start_time = time.time()

        try:
            with self.session() as session:
                if read_only:
                    result = session.run(query_str, **params)
                else:
                    with session.begin_transaction() as tx:
                        result = tx.run(query_str, **params)
                        tx.commit()

                records = [dict(record) for record in result]
                summary = result.consume()

                return QueryResult(
                    records=records,
                    summary={
                        "nodes_created": summary.counters.nodes_created,
                        "nodes_deleted": summary.counters.nodes_deleted,
                        "relationships_created": summary.counters.relationships_created,
                        "relationships_deleted": summary.counters.relationships_deleted,
                        "properties_set": summary.counters.properties_set,
                    },
                    query=query_str,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    success=True,
                )

        except Exception as e:
            return QueryResult(
                records=[],
                summary={},
                query=query_str,
                execution_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error=str(e),
            )

    def _is_read_only_query(self, query: str) -> bool:
        """Check if a Cypher query is read-only."""
        query_upper = query.strip().upper()
        write_keywords = ["CREATE", "MERGE", "DELETE", "SET", "REMOVE", "ADD"]
        return not any(query_upper.startswith(kw) for kw in write_keywords)

    def _execute_batch(
        self, queries: List[str], description: str = ""
    ) -> QueryResult:
        """Execute a batch of Cypher queries."""
        start_time = time.time()
        errors = []

        try:
            with self.transaction() as tx:
                for query in queries:
                    try:
                        tx.run(query)
                    except Exception as e:
                        errors.append(f"Query failed: {e}")
                        _LOGGER.warning("Batch query failed: %s - %s", query, e)

            return QueryResult(
                records=[],
                summary={"queries_executed": len(queries), "errors": len(errors)},
                query=f"Batch: {description}",
                execution_time_ms=(time.time() - start_time) * 1000,
                success=len(errors) == 0,
                error="; ".join(errors) if errors else None,
            )

        except Exception as e:
            return QueryResult(
                records=[],
                summary={},
                query=f"Batch: {description}",
                execution_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error=str(e),
            )

    # ==================== Visualization Data Export ====================

    def export_visualization_data(
        self,
        root_node: Optional[str] = None,
        max_nodes: int = 500,
        max_edges: int = 1000,
        include_properties: bool = False,
    ) -> Dict[str, Any]:
        """
        Export graph data for visualization (D3.js, Cytoscape, etc.).

        Args:
            root_node: Optional root node ID for subgraph extraction.
            max_nodes: Maximum number of nodes to return.
            max_edges: Maximum number of edges to return.
            include_properties: Whether to include node properties.

        Returns:
            Dictionary with nodes and edges for visualization.
        """
        if root_node:
            # Get subgraph around root node
            cypher = CypherQuery(
                query="""
                MATCH (root {id: $root_id})
                OPTIONAL MATCH (root)-[r]-(neighbor)
                WITH root, collect(DISTINCT neighbor) AS neighbors
                UNWIND [root] + neighbors AS node
                WITH collect(DISTINCT node) AS nodes
                UNWIND nodes AS n
                MATCH (n)-[rel]-(m)
                WHERE m IN nodes
                RETURN n, rel, m
                LIMIT $max_edges
                """,
                parameters={"root_id": root_node, "max_edges": max_edges},
                description="Export subgraph for visualization",
            )
        else:
            # Get full graph (limited)
            cypher = CypherQuery(
                query="""
                MATCH (n)
                WITH n LIMIT $max_nodes
                MATCH (n)-[r]-(m)
                WHERE ID(n) < ID(m)
                RETURN n, r, m
                LIMIT $max_edges
                """,
                parameters={"max_nodes": max_nodes, "max_edges": max_edges},
                description="Export graph for visualization",
            )

        result = self.execute(cypher)

        if not result.success:
            return {
                "nodes": [],
                "edges": [],
                "error": result.error,
                "success": False,
            }

        # Transform to visualization format
        nodes_dict = {}
        edges_list = []

        for record in result.records:
            # Process source node
            n = record.get("n")
            if n and n["id"] not in nodes_dict:
                nodes_dict[n["id"]] = self._node_to_viz_format(n, include_properties)

            # Process target node
            m = record.get("m")
            if m and m["id"] not in nodes_dict:
                nodes_dict[m["id"]] = self._node_to_viz_format(m, include_properties)

            # Process relationship
            rel = record.get("r") or record.get("rel")
            if rel:
                edges_list.append(self._rel_to_viz_format(rel))

        return {
            "nodes": list(nodes_dict.values()),
            "edges": edges_list,
            "node_count": len(nodes_dict),
            "edge_count": len(edges_list),
            "success": True,
            "execution_time_ms": result.execution_time_ms,
        }

    def _node_to_viz_format(
        self, node: Any, include_properties: bool = False
    ) -> Dict[str, Any]:
        """Convert Neo4j node to visualization format."""
        labels = list(node.labels)
        node_type = labels[0] if labels else "Node"

        viz_node = {
            "id": node["id"],
            "label": node.get("label", node["id"]),
            "type": node.get("type", node_type.lower()),
            "groups": labels,
            "size": self._calculate_node_size(node_type),
            "color": self._get_node_color(node_type),
        }

        if include_properties:
            viz_node["properties"] = json.loads(node.get("properties", "{}"))

        return viz_node

    def _rel_to_viz_format(self, rel: Any) -> Dict[str, Any]:
        """Convert Neo4j relationship to visualization format."""
        # Get relationship type from available properties
        rel_type = rel.type if hasattr(rel, "type") else "RELATED"

        return {
            "source": rel.start_node["id"]
            if hasattr(rel, "start_node")
            else rel.get("source", ""),
            "target": rel.end_node["id"]
            if hasattr(rel, "end_node")
            else rel.get("target", ""),
            "type": rel_type,
            "label": rel_type.replace("_", " ").title(),
            "weight": rel.get("weight", 1.0),
            "confidence": rel.get("confidence", 1.0),
        }

    def _calculate_node_size(self, node_type: str) -> int:
        """Calculate node size based on type."""
        size_map = {
            "Entity": 20,
            "Zone": 25,
            "Area": 22,
            "Service": 18,
            "Mood": 15,
            "Pattern": 16,
            "Context": 14,
        }
        return size_map.get(node_type, 12)

    def _get_node_color(self, node_type: str) -> str:
        """Get node color based on type."""
        color_map = {
            "Entity": "#4fc3f7",  # Light blue
            "Zone": "#81c784",  # Light green
            "Area": "#4db6ac",  # Teal
            "Service": "#ffb74d",  # Orange
            "Mood": "#ce93d8",  # Purple
            "Pattern": "#ff8a65",  # Deep orange
            "Context": "#90caf9",  # Blue
        }
        return color_map.get(node_type, "#999999")

    # ==================== Graph Analytics ====================

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get comprehensive graph statistics."""
        cypher = CypherQuery(
            query="""
            MATCH (n)
            OPTIONAL MATCH ()-[r]->()
            WITH
              count(DISTINCT n) AS node_count,
              count(DISTINCT r) AS edge_count
            RETURN node_count, edge_count
            """,
            description="Get graph statistics",
        )

        result = self.execute(cypher)

        if not result.success or not result.records:
            return {"error": result.error, "success": False}

        record = result.records[0]
        return {
            "node_count": record.get("node_count", 0),
            "edge_count": record.get("edge_count", 0),
            "density": self._calculate_density(
                record.get("node_count", 0), record.get("edge_count", 0)
            ),
            "success": True,
            "execution_time_ms": result.execution_time_ms,
        }

    def _calculate_density(self, nodes: int, edges: int) -> float:
        """Calculate graph density."""
        if nodes < 2:
            return 0.0
        max_edges = nodes * (nodes - 1)
        return round(edges / max_edges, 4) if max_edges > 0 else 0.0

    def find_central_nodes(self, top_k: int = 10) -> QueryResult:
        """
        Find the most central nodes in the graph.

        Args:
            top_k: Number of top nodes to return.

        Returns:
            QueryResult with central nodes.
        """
        cypher = CypherQuery(
            query="""
            MATCH (n)
            WITH n, size((n)--()) AS degree
            ORDER BY degree DESC
            LIMIT $top_k
            RETURN n.id AS id, n.label AS label, degree
            """,
            parameters={"top_k": top_k},
            description="Find central nodes by degree",
        )

        return self.execute(cypher)

    def find_communities(self, min_size: int = 3) -> QueryResult:
        """
        Detect communities using connected components.

        Args:
            min_size: Minimum community size.

        Returns:
            QueryResult with communities.
        """
        cypher = CypherQuery(
            query="""
            MATCH (n)
            WITH collect(n) AS nodes
            CALL gds.wcc.stream({
                nodeProjection: '*',
                relationshipProjection: {
                    ALL: {
                        type: '*',
                        orientation: 'UNDIRECTED'
                    }
                }
            })
            YIELD componentId, nodeId
            WITH componentId, count(*) AS size
            WHERE size >= $min_size
            RETURN componentId, size
            ORDER BY size DESC
            """,
            parameters={"min_size": min_size},
            description="Find communities",
        )

        return self.execute(cypher)

    # ==================== Cleanup ====================

    def clear_graph(self) -> QueryResult:
        """Clear all nodes and edges from the graph."""
        cypher = CypherQuery(
            query="""
            MATCH (n)
            DETACH DELETE n
            """,
            read_only=False,
            description="Clear entire graph",
        )

        return self.execute(cypher)

    def remove_orphan_nodes(self) -> QueryResult:
        """Remove nodes with no relationships."""
        cypher = CypherQuery(
            query="""
            MATCH (n)
            WHERE NOT (n)--()
            DETACH DELETE n
            """,
            read_only=False,
            description="Remove orphan nodes",
        )

        return self.execute(cypher)


# ==================== Convenience Functions ====================


def get_neo4j_adapter(config: Optional[Neo4jConfig] = None) -> Neo4jAdapter:
    """
    Get a configured Neo4j adapter instance.

    Args:
        config: Optional configuration override.

    Returns:
        Configured Neo4jAdapter instance.
    """
    adapter = Neo4jAdapter(config)
    adapter.connect()
    return adapter


def export_to_neo4j(
    nodes: List[Node], edges: List[Edge], config: Optional[Neo4jConfig] = None
) -> Dict[str, Any]:
    """
    Convenience function to export brain graph to Neo4j.

    Args:
        nodes: List of nodes to export.
        edges: List of edges to export.
        config: Optional Neo4j configuration.

    Returns:
        Export statistics.
    """
    adapter = get_neo4j_adapter(config)
    try:
        return adapter.export_brain_graph(nodes, edges)
    finally:
        adapter.disconnect()


def get_visualization_data(
    root_node: Optional[str] = None,
    config: Optional[Neo4jConfig] = None,
) -> Dict[str, Any]:
    """
    Get graph data for visualization.

    Args:
        root_node: Optional root node for subgraph.
        config: Optional Neo4j configuration.

    Returns:
        Visualization data with nodes and edges.
    """
    adapter = get_neo4j_adapter(config)
    try:
        return adapter.export_visualization_data(root_node=root_node)
    finally:
        adapter.disconnect()
