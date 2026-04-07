"""Brain module — Knowledge graph and reasoning for PilotSuite.

Provides Neo4j/NetworkX backed knowledge graph with Entity-Relation-Entity schema,
temporal reasoning, and SPARQL-like query capabilities.
"""

from .graph_store import (
    BrainGraphStore,
    Entity,
    Relationship,
    TemporalContext
)

from .graph_api import (
    BrainGraphAPI,
    GRAPHQL_SCHEMA
)

__all__ = [
    "BrainGraphStore",
    "BrainGraphAPI",
    "Entity",
    "Relationship",
    "TemporalContext",
    "GRAPHQL_SCHEMA"
]
