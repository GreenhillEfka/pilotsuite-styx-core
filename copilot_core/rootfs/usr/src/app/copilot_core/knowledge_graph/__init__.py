"""Knowledge Graph module for PilotSuite.

Provides Neo4j-backed graph storage with SQLite fallback for capturing
relationships between entities, patterns, moods, and contexts.

Phase 1 (v0.5.0): Foundation with Neo4j/SQLite dual backend.
Phase 2 (v0.6.0): Neo4j adapter with advanced Cypher query support.
"""

from .models import NodeType, EdgeType, Node, Edge, GraphQuery
from .graph_store import GraphStore, get_graph_store
from .builder import GraphBuilder
from .pattern_importer import PatternImporter
from .sparql_endpoint import SPARQLParser, SPARQLExecutor, execute_sparql, validate_sparql_query, sparql_bp
from .neo4j_adapter import (
    Neo4jAdapter,
    Neo4jConfig,
    CypherQuery,
    QueryResult,
    get_neo4j_adapter,
    export_to_neo4j,
    get_visualization_data,
)
from .cypher_adapter import (
    CypherBuilder,
    CypherTemplates,
    CypherValidator,
    CypherOptimizer,
)

__all__ = [
    "NodeType",
    "EdgeType", 
    "Node",
    "Edge",
    "GraphQuery",
    "GraphStore",
    "get_graph_store",
    "GraphBuilder",
    "PatternImporter",
    "SPARQLParser",
    "SPARQLExecutor",
    "execute_sparql",
    "validate_sparql_query",
    "sparql_bp",
    # Neo4j adapter
    "Neo4jAdapter",
    "Neo4jConfig",
    "CypherQuery",
    "QueryResult",
    "get_neo4j_adapter",
    "export_to_neo4j",
    "get_visualization_data",
    # Cypher adapter
    "CypherBuilder",
    "CypherTemplates",
    "CypherValidator",
    "CypherOptimizer",
]