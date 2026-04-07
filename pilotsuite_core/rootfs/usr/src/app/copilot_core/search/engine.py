"""Search Engine — Slice 32.

Full-text search for PilotSuite Core.

Features:
- Entity and event search
- Fuzzy matching
- Faceted search
- Search analytics
- Index management
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class SearchMatchType(Enum):
    """Type of search match."""
    EXACT = "exact"
    FUZZY = "fuzzy"
    PREFIX = "prefix"
    CONTAINS = "contains"
    REGEX = "regex"


@dataclass
class SearchIndex:
    """Search index for a document."""
    index_id: str
    document_id: str
    document_type: str
    content: str  # Indexed content
    metadata: Dict[str, Any]
    tokens: Set[str]  # Tokenized content
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index_id": self.index_id,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "metadata": self.metadata,
            "token_count": len(self.tokens),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class SearchResult:
    """Search result."""
    document_id: str
    document_type: str
    score: float
    matched_tokens: List[str]
    highlights: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_type": self.document_type,
            "score": round(self.score, 4),
            "matched_tokens": self.matched_tokens,
            "highlights": self.highlights,
            "metadata": self.metadata,
        }


@dataclass
class SearchQuery:
    """Search query definition."""
    query_text: str
    match_type: SearchMatchType = SearchMatchType.FUZZY
    document_types: Optional[List[str]] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 50
    offset: int = 0
    min_score: float = 0.1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_text": self.query_text,
            "match_type": self.match_type.value,
            "document_types": self.document_types,
            "filters": self.filters,
            "limit": self.limit,
            "offset": self.offset,
            "min_score": self.min_score,
        }


class SearchEngine:
    """Full-text search engine."""
    
    def __init__(self, fuzzy_threshold: float = 0.6):
        self._indices: Dict[str, SearchIndex] = {}
        self._index_counter = 0
        self._fuzzy_threshold = fuzzy_threshold
        
        # Search statistics
        self._stats = {
            "searches": 0,
            "documents_indexed": 0,
            "total_queries": 0,
        }
    
    def index_document(self, document_id: str, document_type: str,
                      content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Index a document for search."""
        # Remove existing index for this document
        self.remove_document(document_id)
        
        self._index_counter += 1
        index_id = f"idx_{self._index_counter}"
        
        # Tokenize content
        tokens = self._tokenize(content)
        
        index = SearchIndex(
            index_id=index_id,
            document_id=document_id,
            document_type=document_type,
            content=content,
            metadata=metadata or {},
            tokens=tokens,
        )
        
        self._indices[index_id] = index
        self._stats["documents_indexed"] += 1
        
        logger.debug("Document indexed: %s (%s)", document_id, document_type)
        
        return index_id
    
    def _tokenize(self, content: str) -> Set[str]:
        """Tokenize content for indexing."""
        # Convert to lowercase
        content = content.lower()
        
        # Remove special characters
        content = re.sub(r'[^\w\s]', ' ', content)
        
        # Split into tokens
        tokens = set(content.split())
        
        # Remove very short tokens
        tokens = {t for t in tokens if len(t) >= 3}
        
        return tokens
    
    def remove_document(self, document_id: str) -> bool:
        """Remove a document from the index."""
        removed = False
        for index_id, index in list(self._indices.items()):
            if index.document_id == document_id:
                del self._indices[index_id]
                self._stats["documents_indexed"] -= 1
                removed = True
        
        return removed
    
    def search(self, query_text: str,
              document_types: Optional[List[str]] = None,
              filters: Optional[Dict[str, Any]] = None,
              limit: int = 50,
              match_type: str = "fuzzy",
              min_score: float = 0.1) -> List[SearchResult]:
        """Search indexed documents."""
        self._stats["searches"] += 1
        self._stats["total_queries"] += 1
        
        query = SearchQuery(
            query_text=query_text,
            match_type=SearchMatchType(match_type),
            document_types=document_types,
            filters=filters or {},
            limit=limit,
            min_score=min_score,
        )
        
        results = []
        query_tokens = self._tokenize(query_text)
        
        for index in self._indices.values():
            # Filter by document type
            if query.document_types and index.document_type not in query.document_types:
                continue
            
            # Apply filters
            if not self._matches_filters(index.metadata, query.filters):
                continue
            
            # Calculate match score
            score, matched_tokens = self._calculate_score(index, query_tokens, query.match_type)
            
            if score >= query.min_score:
                highlights = self._generate_highlights(index.content, matched_tokens)
                
                result = SearchResult(
                    document_id=index.document_id,
                    document_type=index.document_type,
                    score=score,
                    matched_tokens=list(matched_tokens),
                    highlights=highlights,
                    metadata=index.metadata,
                )
                results.append(result)
        
        # Sort by score (highest first)
        results.sort(key=lambda r: r.score, reverse=True)
        
        return results[:query.limit]
    
    def _calculate_score(self, index: SearchIndex, query_tokens: Set[str],
                        match_type: SearchMatchType) -> tuple:
        """Calculate match score for an index."""
        matched_tokens = set()

        if match_type == SearchMatchType.EXACT:
            matched_tokens = query_tokens & index.tokens
            score = len(matched_tokens) / len(query_tokens) if query_tokens else 0.0

        elif match_type == SearchMatchType.FUZZY:
            total_similarity = 0.0
            for query_token in query_tokens:
                best_similarity = 0.0
                best_token = None
                for index_token in index.tokens:
                    similarity = self._fuzzy_match(query_token, index_token)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_token = index_token
                if best_similarity >= self._fuzzy_threshold and best_token is not None:
                    matched_tokens.add(best_token)
                    total_similarity += best_similarity
            score = total_similarity / len(query_tokens) if query_tokens else 0.0

        elif match_type == SearchMatchType.PREFIX:
            for query_token in query_tokens:
                for index_token in index.tokens:
                    if index_token.startswith(query_token):
                        matched_tokens.add(index_token)
            score = len(matched_tokens) / len(query_tokens) if query_tokens else 0.0

        elif match_type == SearchMatchType.CONTAINS:
            for query_token in query_tokens:
                for index_token in index.tokens:
                    if query_token in index_token:
                        matched_tokens.add(index_token)
            score = len(matched_tokens) / len(query_tokens) if query_tokens else 0.0

        else:
            score = 0.0

        # Boost exact matches without fully flattening fuzzy-score differences.
        exact_matches = len(query_tokens & index.tokens)
        score += exact_matches * 0.1

        return min(score, 1.0), matched_tokens

    def _fuzzy_match(self, s1: str, s2: str) -> float:
        """Calculate fuzzy match similarity (Levenshtein-based)."""
        if s1 == s2:
            return 1.0
        
        len1, len2 = len(s1), len(s2)
        
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Simple Levenshtein distance
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if s1[i-1] == s2[j-1]:
                    cost = 0
                else:
                    cost = 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,  # deletion
                    matrix[i][j-1] + 1,  # insertion
                    matrix[i-1][j-1] + cost,  # substitution
                )
        
        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        
        return 1.0 - (distance / max_len)
    
    def _generate_highlights(self, content: str, matched_tokens: Set[str]) -> List[str]:
        """Generate highlights from content."""
        highlights = []
        content_lower = content.lower()
        
        for token in matched_tokens:
            # Find occurrences in content
            start = 0
            while True:
                pos = content_lower.find(token, start)
                if pos == -1:
                    break
                
                # Extract surrounding context
                context_start = max(0, pos - 30)
                context_end = min(len(content), pos + len(token) + 30)
                
                highlight = content[context_start:context_end]
                if context_start > 0:
                    highlight = "..." + highlight
                if context_end < len(content):
                    highlight = highlight + "..."
                
                if highlight not in highlights:
                    highlights.append(highlight)
                
                start = pos + 1
                
                if len(highlights) >= 3:
                    break
        
        return highlights[:3]
    
    def _matches_filters(self, metadata: Dict[str, Any],
                        filters: Dict[str, Any]) -> bool:
        """Check if metadata matches filters."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            
            if metadata[key] != value:
                return False
        
        return True
    
    def get_index(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get index for a document."""
        for index in self._indices.values():
            if index.document_id == document_id:
                return index.to_dict()
        return None
    
    def get_all_indices(self, document_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all indices."""
        indices = list(self._indices.values())
        
        if document_type:
            indices = [i for i in indices if i.document_type == document_type]
        
        return [i.to_dict() for i in indices]
    
    def get_search_facets(self, document_type: Optional[str] = None) -> Dict[str, Any]:
        """Get search facets for filtering."""
        facets = {
            "document_types": {},
            "metadata_fields": {},
        }
        
        indices = list(self._indices.values())
        
        if document_type:
            indices = [i for i in indices if i.document_type == document_type]
        
        # Count document types
        for index in indices:
            doc_type = index.document_type
            facets["document_types"][doc_type] = facets["document_types"].get(doc_type, 0) + 1
            
            # Collect metadata fields
            for key, value in index.metadata.items():
                if key not in facets["metadata_fields"]:
                    facets["metadata_fields"][key] = {}
                
                value_str = str(value)
                facets["metadata_fields"][key][value_str] = \
                    facets["metadata_fields"][key].get(value_str, 0) + 1
        
        return facets
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """Get search statistics."""
        return {
            **self._stats,
            "total_indices": len(self._indices),
            "unique_tokens": len(set().union(*[i.tokens for i in self._indices.values()])) if self._indices else 0,
        }
    
    def clear_indices(self) -> int:
        """Clear all indices."""
        count = len(self._indices)
        self._indices.clear()
        self._stats["documents_indexed"] = 0
        logger.info("Cleared %d indices", count)
        return count
    
    def rebuild_index(self, document_id: str, content: str,
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Rebuild index for a document."""
        if not self.remove_document(document_id):
            return False
        
        self.index_document(document_id, "unknown", content, metadata)
        return True


def create_search_engine(fuzzy_threshold: float = 0.6) -> SearchEngine:
    """Factory function to create search engine."""
    return SearchEngine(fuzzy_threshold=fuzzy_threshold)
