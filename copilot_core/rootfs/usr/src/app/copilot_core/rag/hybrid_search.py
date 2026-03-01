"""Hybrid Search Engine for RAG (Retrieval-Augmented Generation).

Combines BM25 (lexical search) with vector similarity search using
Reciprocal Rank Fusion (RRF) for optimal re-ranking.

Features:
- BM25 + Vector Search combination
- Multi-Query support (parallel search queries)
- Reciprocal Rank Fusion (RRF) for re-ranking
- Performance optimized for <100ms response time
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

_LOGGER = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """Result from hybrid search."""
    
    id: str
    score: float
    bm25_score: float = 0.0
    vector_score: float = 0.0
    rrf_score: float = 0.0
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    rank_bm25: int = 0
    rank_vector: int = 0
    final_rank: int = 0


@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search."""
    
    # RRF parameter (typically 60)
    rrf_k: int = 60
    
    # Weights for BM25 and vector search (0.0-1.0, sum to 1.0)
    bm25_weight: float = 0.5
    vector_weight: float = 0.5
    
    # Number of results to return
    top_k: int = 10
    
    # BM25 parameters
    bm25_k1: float = 1.5  # Term frequency saturation
    bm25_b: float = 0.75  # Length normalization
    
    # Minimum similarity threshold for vector search
    vector_threshold: float = 0.5
    
    # Enable multi-query (parallel search)
    multi_query_enabled: bool = True
    
    # Number of parallel queries for multi-query
    multi_query_count: int = 3
    
    # Performance settings
    use_cache: bool = True
    cache_ttl_seconds: int = 300


class BM25Index:
    """BM25 (Best Matching 25) full-text search index.
    
    Optimized for fast lexical search with configurable parameters.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 index.
        
        Args:
            k1: Term frequency saturation parameter (default 1.5)
            b: Length normalization parameter (default 0.75)
        """
        self.k1 = k1
        self.b = b
        
        # Index structures
        self._doc_freq: Dict[str, int] = defaultdict(int)  # DF(t)
        self._doc_lengths: Dict[str, int] = {}  # |d|
        self._doc_contents: Dict[str, str] = {}  # Document content
        self._term_freqs: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # TF(t,d)
        self._num_docs: int = 0
        self._avg_doc_length: float = 0.0
        
        # Precompiled regex for tokenization
        self._token_pattern = re.compile(r'\b\w+\b', re.UNICODE)
        
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        return self._token_pattern.findall(text.lower())
    
    def add_document(self, doc_id: str, content: str) -> None:
        """Add a document to the index.
        
        Args:
            doc_id: Unique document identifier
            content: Document text content
        """
        tokens = self._tokenize(content)
        doc_length = len(tokens)
        
        # Update document length
        if doc_id in self._doc_lengths:
            old_length = self._doc_lengths[doc_id]
            self._avg_doc_length = (
                (self._avg_doc_length * self._num_docs - old_length + doc_length) /
                self._num_docs
            )
        else:
            self._num_docs += 1
            self._avg_doc_length = (
                (self._avg_doc_length * (self._num_docs - 1) + doc_length) /
                self._num_docs
            )
        
        self._doc_lengths[doc_id] = doc_length
        self._doc_contents[doc_id] = content
        
        # Update term frequencies and document frequencies
        term_counts = defaultdict(int)
        for token in tokens:
            term_counts[token] += 1
            
        for term, freq in term_counts.items():
            self._term_freqs[term][doc_id] = freq
            if freq > 0:
                self._doc_freq[term] += 1
    
    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from the index.
        
        Args:
            doc_id: Document identifier to remove
            
        Returns:
            True if removed, False if not found
        """
        if doc_id not in self._doc_lengths:
            return False
        
        # Remove term frequencies
        for term in list(self._term_freqs.keys()):
            if doc_id in self._term_freqs[term]:
                del self._term_freqs[term][doc_id]
                if not self._term_freqs[term]:
                    del self._term_freqs[term]
                    del self._doc_freq[term]
        
        # Update statistics
        doc_length = self._doc_lengths[doc_id]
        self._num_docs -= 1
        if self._num_docs > 0:
            self._avg_doc_length = (
                (self._avg_doc_length * (self._num_docs + 1) - doc_length) /
                self._num_docs
            )
        else:
            self._avg_doc_length = 0.0
        
        # Remove document
        del self._doc_lengths[doc_id]
        del self._doc_contents[doc_id]
        
        return True
    
    def bm25_score(self, term: str, doc_id: str) -> float:
        """Calculate BM25 score for a term in a document.
        
        BM25(t,d) = IDF(t) * (TF(t,d) * (k1 + 1)) / (TF(t,d) + k1 * (1 - b + b * |d|/avgdl))
        
        Args:
            term: Search term
            doc_id: Document identifier
            
        Returns:
            BM25 score
        """
        if doc_id not in self._doc_lengths:
            return 0.0
        
        # Term frequency
        tf = self._term_freqs[term].get(doc_id, 0)
        if tf == 0:
            return 0.0
        
        # Document length
        doc_len = self._doc_lengths[doc_id]
        
        # IDF calculation: log((N - DF(t) + 0.5) / (DF(t) + 0.5) + 1)
        df = self._doc_freq.get(term, 0)
        idf = math.log((self._num_docs - df + 0.5) / (df + 0.5) + 1)
        
        # BM25 formula
        numerator = tf * (self.k1 + 1)
        denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self._avg_doc_length)
        
        return idf * (numerator / denominator)
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """Search for documents matching the query.
        
        Args:
            query: Search query string
            top_k: Number of top results to return
            
        Returns:
            List of (doc_id, score) tuples sorted by score descending
        """
        tokens = self._tokenize(query)
        if not tokens:
            return []
        
        # Accumulate scores for each document
        scores: Dict[str, float] = defaultdict(float)
        
        for token in tokens:
            for doc_id in self._term_freqs[token]:
                scores[doc_id] += self.bm25_score(token, doc_id)
        
        # Sort by score and return top_k
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]
    
    def get_document(self, doc_id: str) -> Optional[str]:
        """Get document content by ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Document content or None if not found
        """
        return self._doc_contents.get(doc_id)


def rrf_fusion(
    results_lists: List[List[Tuple[str, float]]],
    k: int = 60,
) -> Dict[str, float]:
    """Reciprocal Rank Fusion (RRF) to combine multiple result rankings.
    
    RRF(d) = Σ (1 / (k + rank(d))) for each result list
    
    Args:
        results_lists: List of ranked result lists, each containing (doc_id, score)
        k: RRF parameter (typically 60)
        
    Returns:
        Dictionary mapping doc_id to RRF score
    """
    rrf_scores: Dict[str, float] = defaultdict(float)
    
    for results in results_lists:
        for rank, (doc_id, _) in enumerate(results, start=1):
            rrf_scores[doc_id] += 1.0 / (k + rank)
    
    return dict(rrf_scores)


class HybridSearchEngine:
    """Hybrid search engine combining BM25 and vector search.
    
    Features:
    - BM25 lexical search
    - Vector similarity search
    - Reciprocal Rank Fusion (RRF) re-ranking
    - Multi-query support (parallel queries)
    - Performance optimized for <100ms response time
    """
    
    def __init__(
        self,
        config: Optional[HybridSearchConfig] = None,
        vector_store=None,
    ):
        """Initialize hybrid search engine.
        
        Args:
            config: Search configuration
            vector_store: VectorStore instance for vector search
        """
        self.config = config or HybridSearchConfig()
        self._bm25_index = BM25Index(
            k1=self.config.bm25_k1,
            b=self.config.bm25_b,
        )
        self._vector_store = vector_store
        
        # Caching
        self._cache: Dict[str, Tuple[List[HybridSearchResult], float]] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        _LOGGER.info("HybridSearchEngine initialized with config: %s", self.config)
    
    def add_document(self, doc_id: str, content: str, vector: Optional[List[float]] = None) -> None:
        """Add a document to the search index.
        
        Args:
            doc_id: Unique document identifier
            content: Document text content
            vector: Optional embedding vector for vector search
        """
        self._bm25_index.add_document(doc_id, content)
        
        if vector and self._vector_store:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    self._vector_store.upsert(
                        entry_id=doc_id,
                        vector=vector,
                        entry_type="rag_document",
                        metadata={"content": content[:500]},  # Store preview
                    )
                )
            finally:
                loop.close()
    
    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from the search index.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if removed, False if not found
        """
        return self._bm25_index.remove_document(doc_id)
    
    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[HybridSearchResult]:
        """Perform hybrid search combining BM25 and vector search.
        
        Args:
            query: Search query string
            top_k: Number of results to return (default from config)
            filters: Optional filters for vector search
            
        Returns:
            List of HybridSearchResult sorted by combined score
        """
        start_time = time.time()
        top_k = top_k or self.config.top_k
        
        # Check cache
        if self.config.use_cache:
            cache_key = f"{query}:{top_k}"
            if cache_key in self._cache:
                cached_results, cache_time = self._cache[cache_key]
                if (time.time() - cache_time) < self.config.cache_ttl_seconds:
                    return cached_results
        
        # Run BM25 and vector search in parallel
        bm25_task = asyncio.create_task(self._bm25_search(query, top_k * 2))
        vector_task = asyncio.create_task(self._vector_search(query, top_k * 2, filters))
        
        bm25_results, vector_results = await asyncio.gather(bm25_task, vector_task)
        
        # Apply RRF fusion
        rrf_scores = rrf_fusion(
            [bm25_results, vector_results],
            k=self.config.rrf_k,
        )
        
        # Build final results with combined scores
        results_dict: Dict[str, HybridSearchResult] = {}
        
        # Add BM25 results
        for rank, (doc_id, bm25_score) in enumerate(bm25_results, start=1):
            results_dict[doc_id] = HybridSearchResult(
                id=doc_id,
                score=bm25_score * self.config.bm25_weight,
                bm25_score=bm25_score,
                rank_bm25=rank,
                content=self._bm25_index.get_document(doc_id) or "",
            )
        
        # Add/merge vector results
        for rank, (doc_id, vector_score) in enumerate(vector_results, start=1):
            if doc_id in results_dict:
                result = results_dict[doc_id]
                result.vector_score = vector_score
                result.rank_vector = rank
                # Combined score with weights
                result.score = (
                    result.bm25_score * self.config.bm25_weight +
                    vector_score * self.config.vector_weight
                )
            else:
                results_dict[doc_id] = HybridSearchResult(
                    id=doc_id,
                    score=vector_score * self.config.vector_weight,
                    vector_score=vector_score,
                    rank_vector=rank,
                )
        
        # Apply RRF scores
        for doc_id, rrf_score in rrf_scores.items():
            if doc_id in results_dict:
                results_dict[doc_id].rrf_score = rrf_score
        
        # Sort by RRF score (primary) then combined score (secondary)
        sorted_results = sorted(
            results_dict.values(),
            key=lambda r: (r.rrf_score, r.score),
            reverse=True,
        )[:top_k]
        
        # Assign final ranks
        for i, result in enumerate(sorted_results, start=1):
            result.final_rank = i
        
        # Calculate execution time
        exec_time_ms = (time.time() - start_time) * 1000
        
        if exec_time_ms > 100:
            _LOGGER.warning("Hybrid search took %.2fms (target: <100ms)", exec_time_ms)
        else:
            _LOGGER.debug("Hybrid search completed in %.2fms", exec_time_ms)
        
        # Cache results
        if self.config.use_cache:
            self._cache[f"{query}:{top_k}"] = (sorted_results, time.time())
        
        return sorted_results
    
    async def search_multi_query(
        self,
        queries: List[str],
        top_k: Optional[int] = None,
    ) -> List[HybridSearchResult]:
        """Perform multi-query hybrid search (parallel queries).
        
        Sends multiple variations of the query in parallel and fuses results.
        
        Args:
            queries: List of query variations
            top_k: Number of results to return
            
        Returns:
            List of HybridSearchResult fused from all queries
        """
        if not self.config.multi_query_enabled:
            # Fallback to single query
            return await self.search(queries[0] if queries else "", top_k)
        
        start_time = time.time()
        top_k = top_k or self.config.top_k
        
        # Run all queries in parallel
        tasks = [self.search(query, top_k * 2) for query in queries[:self.config.multi_query_count]]
        results_lists = await asyncio.gather(*tasks)
        
        # Flatten and fuse results using RRF
        all_results: Dict[str, HybridSearchResult] = {}
        
        for results in results_lists:
            for result in results:
                if result.id in all_results:
                    # Keep best scores
                    existing = all_results[result.id]
                    existing.score = max(existing.score, result.score)
                    existing.bm25_score = max(existing.bm25_score, result.bm25_score)
                    existing.vector_score = max(existing.vector_score, result.vector_score)
                    existing.rrf_score += result.rrf_score
                else:
                    all_results[result.id] = result
        
        # Sort by combined score and return top_k
        sorted_results = sorted(
            all_results.values(),
            key=lambda r: r.score,
            reverse=True,
        )[:top_k]
        
        # Assign final ranks
        for i, result in enumerate(sorted_results, start=1):
            result.final_rank = i
        
        exec_time_ms = (time.time() - start_time) * 1000
        _LOGGER.debug("Multi-query search (%d queries) completed in %.2fms", len(queries), exec_time_ms)
        
        return sorted_results
    
    async def _bm25_search(
        self,
        query: str,
        top_k: int,
    ) -> List[Tuple[str, float]]:
        """Perform BM25 search.
        
        Args:
            query: Search query
            top_k: Number of results
            
        Returns:
            List of (doc_id, score) tuples
        """
        return self._bm25_index.search(query, top_k)
    
    async def _vector_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
    ) -> List[Tuple[str, float]]:
        """Perform vector similarity search.
        
        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters
            
        Returns:
            List of (doc_id, score) tuples
        """
        if not self._vector_store:
            return []
        
        try:
            # Generate query embedding (async)
            from copilot_core.vector_store.embeddings import get_embedding_engine
            engine = get_embedding_engine()
            
            loop = asyncio.get_event_loop()
            embedding_result = await loop.run_in_executor(
                self._executor,
                lambda: engine.generate_embedding(query),
            )
            
            query_vector = embedding_result.embedding
            
            # Search vector store
            results = await self._vector_store.search_similar(
                query_vector=query_vector,
                entry_type="rag_document",
                limit=top_k,
                threshold=self.config.vector_threshold,
            )
            
            return [(r.id, r.similarity) for r in results]
            
        except Exception as e:
            _LOGGER.error("Vector search failed: %s", e)
            return []
    
    def clear_cache(self) -> None:
        """Clear the search cache."""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get search engine statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "num_documents": self._bm25_index._num_docs,
            "avg_doc_length": self._bm25_index._avg_doc_length,
            "cache_size": len(self._cache),
            "config": {
                "rrf_k": self.config.rrf_k,
                "bm25_weight": self.config.bm25_weight,
                "vector_weight": self.config.vector_weight,
                "top_k": self.config.top_k,
                "multi_query_enabled": self.config.multi_query_enabled,
            },
        }


# Singleton instance
_HYBRID_SEARCH: Optional[HybridSearchEngine] = None


def get_hybrid_search_engine(
    config: Optional[HybridSearchConfig] = None,
    vector_store=None,
) -> HybridSearchEngine:
    """Get the hybrid search engine singleton.
    
    Args:
        config: Optional configuration
        vector_store: Optional vector store instance
        
    Returns:
        HybridSearchEngine instance
    """
    global _HYBRID_SEARCH
    
    if _HYBRID_SEARCH is None:
        _HYBRID_SEARCH = HybridSearchEngine(config=config, vector_store=vector_store)
    
    return _HYBRID_SEARCH
