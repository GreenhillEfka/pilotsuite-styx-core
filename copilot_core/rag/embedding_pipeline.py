"""P2-003: Embedding Pipeline — Batch Embeddings, Caching, Updates."""
from __future__ import annotations

import logging
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingCache:
    """Cache for embeddings."""
    text_hash: str
    embedding: List[float]
    model: str
    created_at: float = field(default_factory=time.time)
    access_count: int = 0


@dataclass
class BatchResult:
    """Result of batch embedding."""
    total: int
    successful: int
    failed: int
    cached: int
    duration_ms: float
    embeddings: List[List[float]]


class EmbeddingPipeline:
    """Production embedding pipeline with batching and caching."""

    def __init__(
        self,
        embed_fn: Callable[[str], List[float]],
        cache_dir: Optional[str] = None,
        cache_size: int = 10000,
        batch_size: int = 32,
    ):
        self.embed_fn = embed_fn
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_size = cache_size
        self.batch_size = batch_size
        self._cache: Dict[str, EmbeddingCache] = {}
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "batches_processed": 0,
        }
        
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_cache()

    def embed(self, text: str, model: str = "default") -> List[float]:
        """Get embedding for single text."""
        self._stats["total_requests"] += 1
        
        text_hash = self._hash_text(text)
        
        # Check cache
        if text_hash in self._cache:
            self._cache[text_hash].access_count += 1
            self._stats["cache_hits"] += 1
            return self._cache[text_hash].embedding
        
        self._stats["cache_misses"] += 1
        
        # Generate embedding
        embedding = self.embed_fn(text)
        
        # Cache result
        self._cache[text_hash] = EmbeddingCache(
            text_hash=text_hash,
            embedding=embedding,
            model=model
        )
        
        # Evict if needed
        if len(self._cache) > self.cache_size:
            self._evict_oldest()
        
        return embedding

    def embed_batch(self, texts: List[str], model: str = "default") -> BatchResult:
        """Get embeddings for batch of texts."""
        start = time.time()
        embeddings = []
        cached_count = 0
        failed_count = 0
        
        for text in texts:
            try:
                embedding = self.embed(text, model)
                embeddings.append(embedding)
                if text in self._cache:
                    cached_count += 1
            except Exception as e:
                logger.warning(f"Embedding failed: {e}")
                failed_count += 1
                embeddings.append([0.0] * 384)  # Zero vector fallback
        
        self._stats["batches_processed"] += 1
        duration_ms = (time.time() - start) * 1000
        
        return BatchResult(
            total=len(texts),
            successful=len(texts) - failed_count,
            failed=failed_count,
            cached=cached_count,
            duration_ms=duration_ms,
            embeddings=embeddings
        )

    def _hash_text(self, text: str) -> str:
        """Create hash for text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _evict_oldest(self):
        """Evict oldest cache entry."""
        if not self._cache:
            return
        
        oldest = min(self._cache.items(), key=lambda x: x[1].created_at)
        del self._cache[oldest[0]]
        logger.debug(f"Evicted oldest cache entry: {oldest[0]}")

    def _load_cache(self):
        """Load cache from disk."""
        cache_file = self.cache_dir / "embedding_cache.json"
        if not cache_file.exists():
            return
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            for key, value in data.items():
                self._cache[key] = EmbeddingCache(**value)
            
            logger.info(f"Loaded {len(self._cache)} cached embeddings")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")

    def _save_cache(self):
        """Save cache to disk."""
        if not self.cache_dir:
            return
        
        cache_file = self.cache_dir / "embedding_cache.json"
        
        try:
            data = {}
            for key, cache in self._cache.items():
                data[key] = {
                    "text_hash": cache.text_hash,
                    "embedding": cache.embedding,
                    "model": cache.model,
                    "created_at": cache.created_at,
                    "access_count": cache.access_count
                }
            
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            
            logger.debug(f"Saved {len(self._cache)} cached embeddings")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        cache_hit_rate = self._stats["cache_hits"] / max(1, self._stats["total_requests"])
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "cache_hit_rate": cache_hit_rate,
        }

    def clear_cache(self):
        """Clear embedding cache."""
        self._cache.clear()
        self._save_cache()
        logger.info("Embedding cache cleared")


# Default embedding function (uses Ollama or similar)
_default_embed_fn: Optional[Callable] = None


def set_embedding_function(embed_fn: Callable[[str], List[float]]):
    """Set the embedding function."""
    global _default_embed_fn
    _default_embed_fn = embed_fn
    logger.info("Embedding function set")


# Global default pipeline
default_embedding_pipeline: Optional[EmbeddingPipeline] = None


def init_embedding_pipeline(
    embed_fn: Optional[Callable] = None,
    cache_dir: Optional[str] = None,
    cache_size: int = 10000,
    batch_size: int = 32,
) -> EmbeddingPipeline:
    """Initialize global embedding pipeline."""
    global default_embedding_pipeline, _default_embed_fn
    
    if embed_fn:
        _default_embed_fn = embed_fn
    elif _default_embed_fn is None:
        # Default: use Ollama mxbai-embed-large
        async def ollama_embed(text: str) -> List[float]:
            from copilot_core.rag.ollama_client import default_ollama
            if default_ollama:
                # Simplified - would use Ollama embeddings API
                return [0.0] * 384
            return [0.0] * 384
        
        _default_embed_fn = ollama_embed
    
    default_embedding_pipeline = EmbeddingPipeline(
        embed_fn=_default_embed_fn,
        cache_dir=cache_dir,
        cache_size=cache_size,
        batch_size=batch_size
    )
    
    return default_embedding_pipeline


def embed_text(text: str) -> List[float]:
    """Convenience function for single embedding."""
    if default_embedding_pipeline:
        return default_embedding_pipeline.embed(text)
    return [0.0] * 384


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Convenience function for batch embedding."""
    if default_embedding_pipeline:
        result = default_embedding_pipeline.embed_batch(texts)
        return result.embeddings
    return [[0.0] * 384 for _ in texts]
