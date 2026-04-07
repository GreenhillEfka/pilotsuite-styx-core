"""Semantic Search — Vector Search, Hybrid Search, Filters, Facets."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import math
import time

logger = logging.getLogger(__name__)


class SearchType(Enum):
    """Search types."""
    SEMANTIC = "semantic"  # Vector similarity
    KEYWORD = "keyword"  # Full-text search
    HYBRID = "hybrid"  # Combined
    FILTERED = "filtered"  # With filters


@dataclass
class SearchDocument:
    """Searchable document."""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: float = field(default_factory=lambda: time.time())
    score: float = 0.0


@dataclass
class SearchResult:
    """Search result."""
    document: SearchDocument
    score: float
    highlights: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class SearchQuery:
    """Search query definition."""
    query_text: str
    search_type: SearchType = SearchType.HYBRID
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 10
    min_score: float = 0.0
    facets: Optional[List[str]] = None


class SemanticSearchEngine:
    """Semantic search engine with hybrid search capabilities."""

    def __init__(self, index_size: int = 10000):
        self._documents: Dict[str, SearchDocument] = {}
        self._index_size = index_size
        self._embedding_dim = 384  # Default embedding dimension

    def index_document(self, doc: SearchDocument) -> str:
        """Index a document for search."""
        if len(self._documents) >= self._index_size:
            # Remove oldest document
            oldest = min(self._documents.values(), key=lambda d: d.created_at)
            del self._documents[oldest.id]
        
        # Generate embedding if not provided
        if not doc.embedding:
            doc.embedding = self._generate_embedding(doc.content)
        
        self._documents[doc.id] = doc
        logger.info(f"Document indexed: {doc.id}")
        return doc.id

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text (simulated)."""
        # In production, would use actual embedding model
        # Simulated embedding based on text hash
        import hashlib
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        # Convert to normalized vector
        embedding = []
        for i in range(self._embedding_dim):
            byte_idx = i % len(hash_bytes)
            value = (hash_bytes[byte_idx] / 255.0) * 2 - 1  # Normalize to [-1, 1]
            embedding.append(value)
        
        # Normalize vector
        magnitude = math.sqrt(sum(x*x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute search query."""
        results = []
        
        # Generate query embedding
        query_embedding = self._generate_embedding(query.query_text)
        
        for doc in self._documents.values():
            # Apply filters
            if query.filters and not self._matches_filters(doc, query.filters):
                continue
            
            # Calculate score based on search type
            if query.search_type == SearchType.SEMANTIC:
                score = self._cosine_similarity(query_embedding, doc.embedding or [])
            elif query.search_type == SearchType.KEYWORD:
                score = self._keyword_score(query.query_text, doc.content)
            elif query.search_type == SearchType.HYBRID:
                semantic_score = self._cosine_similarity(query_embedding, doc.embedding or [])
                keyword_score = self._keyword_score(query.query_text, doc.content)
                score = 0.7 * semantic_score + 0.3 * keyword_score
            else:
                score = 0.0
            
            # Apply minimum score threshold
            if score < query.min_score:
                continue
            
            # Create result
            result = SearchResult(
                document=doc,
                score=score,
                highlights=self._extract_highlights(query.query_text, doc.content),
            )
            results.append(result)
        
        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:query.limit]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)

    def _keyword_score(self, query: str, content: str) -> float:
        """Calculate keyword match score."""
        query_words = query.lower().split()
        content_lower = content.lower()
        
        matches = sum(1 for word in query_words if word in content_lower)
        return matches / max(1, len(query_words))

    def _matches_filters(self, doc: SearchDocument, filters: Dict) -> bool:
        """Check if document matches filters."""
        for key, value in filters.items():
            doc_value = doc.metadata.get(key)
            
            if isinstance(value, dict):
                # Range filter
                if "min" in value and doc_value < value["min"]:
                    return False
                if "max" in value and doc_value > value["max"]:
                    return False
            elif doc_value != value:
                return False
        
        return True

    def _extract_highlights(self, query: str, content: str, context_chars: int = 50) -> List[str]:
        """Extract highlighted snippets from content."""
        highlights = []
        query_words = query.lower().split()
        content_lower = content.lower()
        
        for word in query_words:
            if len(word) < 3:
                continue
            
            idx = content_lower.find(word)
            if idx >= 0:
                start = max(0, idx - context_chars)
                end = min(len(content), idx + len(word) + context_chars)
                snippet = content[start:end].strip()
                if snippet:
                    highlights.append(f"...{snippet}...")
        
        return highlights[:3]  # Limit to 3 highlights

    def get_facets(self, facet_fields: List[str]) -> Dict[str, Dict[str, int]]:
        """Get facet counts for specified fields."""
        facets = {}
        
        for field in facet_fields:
            facet_counts: Dict[str, int] = {}
            
            for doc in self._documents.values():
                value = doc.metadata.get(field)
                if value is not None:
                    value_str = str(value)
                    facet_counts[value_str] = facet_counts.get(value_str, 0) + 1
            
            facets[field] = facet_counts
        
        return facets

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the index."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            logger.info(f"Document deleted: {doc_id}")
            return True
        return False

    def get_document(self, doc_id: str) -> Optional[SearchDocument]:
        """Get document by ID."""
        return self._documents.get(doc_id)

    def bulk_index(self, documents: List[SearchDocument]) -> int:
        """Bulk index multiple documents."""
        count = 0
        for doc in documents:
            self.index_document(doc)
            count += 1
        logger.info(f"Bulk indexed {count} documents")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get search engine statistics."""
        return {
            "total_documents": len(self._documents),
            "index_size": self._index_size,
            "embedding_dim": self._embedding_dim,
            "utilization": len(self._documents) / self._index_size * 100,
        }


# Global default semantic search engine
default_search: Optional[SemanticSearchEngine] = None


def init_semantic_search(index_size: int = 10000) -> SemanticSearchEngine:
    """Initialize global semantic search engine."""
    global default_search
    default_search = SemanticSearchEngine(index_size)
    return default_search
