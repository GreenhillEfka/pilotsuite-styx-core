"""Knowledge Graph module for PilotSuite.

Provides Neo4j-backed graph storage with SQLite fallback for capturing
relationships between entities, patterns, moods, and contexts.

Phase 1 (v0.5.0): Foundation with Neo4j/SQLite dual backend.
"""

from .models import NodeType, EdgeType, Node, Edge, GraphQuery
from .graph_store import GraphStore, get_graph_store
from .builder import GraphBuilder
from .pattern_importer import PatternImporter

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
]