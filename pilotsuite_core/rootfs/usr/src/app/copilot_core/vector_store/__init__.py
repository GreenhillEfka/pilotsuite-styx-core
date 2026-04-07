"""Vector Store Module for Preference Learning & Knowledge Graph.

This module provides embedding generation and similarity search for:
- Entity embeddings (for similar entity discovery)
- User preference vectors (for preference similarity)
- Pattern embeddings (for knowledge graph integration)

Design Doc: docs/VECTOR_STORE_DESIGN.md
"""

from .embeddings import EmbeddingEngine, get_embedding_engine
from .store import VectorStore, get_vector_store

__all__ = [
    "EmbeddingEngine",
    "get_embedding_engine",
    "VectorStore",
    "get_vector_store",
]