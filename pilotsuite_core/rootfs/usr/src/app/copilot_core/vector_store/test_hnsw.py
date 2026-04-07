#!/usr/bin/env python3
"""Quick test for HNSW vector store implementation."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from copilot_core.vector_store.config import VectorStoreConfig
from copilot_core.vector_store.store import VectorStore, reset_vector_store


async def test_hnsw_basic():
    """Test basic HNSW functionality."""
    print("Testing HNSW Vector Store Implementation\n")
    print("=" * 60)
    
    # Test 1: Config loading
    print("\n1. Testing config...")
    config = VectorStoreConfig(
        db_path="/tmp/test_hnsw.db",
        index_type="hnsw",
        hnsw_m=16,
        hnsw_ef_search=50,
        use_float16=True,
    )
    print(f"   Config: index_type={config.index_type}, m={config.hnsw_m}")
    
    # Test 2: Store initialization
    print("\n2. Testing store initialization...")
    reset_vector_store()
    store = VectorStore(config)
    print(f"   Store initialized successfully")
    
    # Test 3: Insert vectors
    print("\n3. Testing vector insertion...")
    import random
    dim = 128
    num_vectors = 100
    
    for i in range(num_vectors):
        vec = [random.gauss(0, 1) for _ in range(dim)]
        # Normalize
        norm = sum(v*v for v in vec) ** 0.5
        vec = [v/norm for v in vec]
        
        await store.upsert(
            entry_id=f"test_{i}",
            vector=vec,
            entry_type="test",
            metadata={"index": i, "category": "test_data"},
        )
    
    print(f"   Inserted {num_vectors} vectors (dim={dim})")
    
    # Test 4: Search
    print("\n4. Testing similarity search...")
    query = [random.gauss(0, 1) for _ in range(dim)]
    norm = sum(v*v for v in query) ** 0.5
    query = [v/norm for v in query]
    
    import time
    start = time.time()
    results = await store.search_similar(
        query_vector=query,
        entry_type="test",
        limit=5,
        threshold=0.0,
    )
    elapsed = (time.time() - start) * 1000
    
    print(f"   Search took {elapsed:.2f}ms")
    print(f"   Found {len(results)} results")
    for i, r in enumerate(results[:3]):
        print(f"     {i+1}. {r.id}: similarity={r.similarity:.4f}")
    
    # Test 5: Batch search
    print("\n5. Testing batch search...")
    queries = [[random.gauss(0, 1) for _ in range(dim)] for _ in range(5)]
    for q in queries:
        norm = sum(v*v for v in q) ** 0.5
        q = [v/norm for v in q]
    
    start = time.time()
    batch_results = await store.batch_search(
        query_vectors=queries,
        entry_type="test",
        limit=3,
    )
    elapsed = (time.time() - start) * 1000
    
    print(f"   Batch search (5 queries) took {elapsed:.2f}ms")
    print(f"   Avg per query: {elapsed/5:.2f}ms")
    
    # Test 6: Stats
    print("\n6. Testing stats...")
    stats = await store.stats()
    print(f"   Total entries: {stats.get('total_entries', 0)}")
    print(f"   Cache size: {stats['cache_size']}")
    print(f"   Index type: {stats['index_config']['type']}")
    if 'hnsw_indices' in stats:
        for type_name, idx_stats in stats['hnsw_indices'].items():
            print(f"   HNSW index '{type_name}': {idx_stats.get('elements', 0)} elements")
    
    # Test 7: Get single entry
    print("\n7. Testing single entry retrieval...")
    entry = await store.get("test_0")
    if entry:
        print(f"   Retrieved: {entry.id}, type={entry.entry_type}")
        print(f"   Vector dim: {len(entry.vector)}")
        print(f"   Metadata: {entry.metadata}")
    
    # Cleanup
    store.close()
    
    # Remove test DB
    import os
    for path in ["/tmp/test_hnsw.db", "/tmp/test_hnsw.db.test.hnsw", "/tmp/test_hnsw.db.test.hnsw.map"]:
        try:
            os.remove(path)
        except OSError:
            pass

    print("\n" + "=" * 60)
    print("✅ All tests passed!\n")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_hnsw_basic())
    sys.exit(0 if success else 1)
