"""Vector Store Configuration.

Configuration for HNSW index parameters and storage options.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class VectorStoreConfig:
    """Configuration for vector store with HNSW support.
    
    Attributes:
        db_path: Path to SQLite database for persistence
        persist: Whether to persist vectors to disk
        cache_size: Maximum number of entries in LRU cache
        similarity_threshold: Default minimum similarity for search
        
        # HNSW Index Configuration
        index_type: Type of index ("hnsw" or "flat")
        hnsw_m: Max number of connections per node (higher = better recall, more memory)
        hnsw_ef_construction: Size of dynamic candidate list during construction
        hnsw_ef_search: Size of dynamic candidate list during search (higher = slower but better)
        hnsw_max_elements: Maximum number of elements in index (0 = unlimited)
        
        # Memory Optimization
        use_float16: Use float16 instead of float32 for memory efficiency
        batch_size: Default batch size for bulk operations
    """
    
    # Basic storage config
    db_path: str = "/data/vector_store.db"
    persist: bool = True
    cache_size: int = 500
    similarity_threshold: float = 0.7
    
    # HNSW index config
    index_type: Literal["hnsw", "flat"] = "hnsw"
    hnsw_m: int = 16  # Typical: 16-64 (higher for high-dimensional vectors)
    hnsw_ef_construction: int = 200  # Typical: 100-400
    hnsw_ef_search: int = 50  # Typical: 20-100
    hnsw_max_elements: int = 100000  # Max elements (0 = unlimited)
    
    # Memory optimization
    use_float16: bool = True
    batch_size: int = 100
    
    @classmethod
    def from_env(cls) -> VectorStoreConfig:
        """Load configuration from environment variables."""
        return cls(
            db_path=os.environ.get("COPILOT_VECTOR_DB_PATH", "/data/vector_store.db"),
            persist=os.environ.get("COPILOT_VECTOR_PERSIST", "true").lower() == "true",
            cache_size=int(os.environ.get("COPILOT_VECTOR_CACHE_SIZE", "500")),
            similarity_threshold=float(os.environ.get("COPILOT_VECTOR_SIMILARITY_THRESHOLD", "0.7")),
            index_type=os.environ.get("COPILOT_VECTOR_INDEX_TYPE", "hnsw"),  # type: ignore
            hnsw_m=int(os.environ.get("COPILOT_VECTOR_HNSW_M", "16")),
            hnsw_ef_construction=int(os.environ.get("COPILOT_VECTOR_HNSW_EF_CONSTRUCTION", "200")),
            hnsw_ef_search=int(os.environ.get("COPILOT_VECTOR_HNSW_EF_SEARCH", "50")),
            hnsw_max_elements=int(os.environ.get("COPILOT_VECTOR_HNSW_MAX_ELEMENTS", "100000")),
            use_float16=os.environ.get("COPILOT_VECTOR_FLOAT16", "true").lower() == "true",
            batch_size=int(os.environ.get("COPILOT_VECTOR_BATCH_SIZE", "100")),
        )
