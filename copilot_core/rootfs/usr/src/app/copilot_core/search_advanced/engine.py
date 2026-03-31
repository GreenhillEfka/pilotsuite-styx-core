"""Search Advanced Engine — Slice 56.

Full-text search for PilotSuite Core.

Features:
- Document indexing
- Full-text search with scoring
- Faceted search
- Filter queries
- Highlighting
- Search suggestions
"""
from __future__ import annotations

import logging
import re
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class FieldType(Enum):
    """Field types for indexing."""
    TEXT = "text"
    KEYWORD = "keyword"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"


@dataclass
class Document:
    """Searchable document."""
    doc_id: str
    fields: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "fields": self.fields,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class SearchResult:
    """Search result with scoring."""
    doc_id: str
    score: float
    fields: Dict[str, Any]
    highlights: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "score": self.score,
            "fields": self.fields,
            "highlights": self.highlights,
        }


@dataclass
class IndexStats:
    """Index statistics."""
    total_documents: int
    total_terms: int
    field_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class InvertedIndex:
    """Inverted index for full-text search."""
    
    def __init__(self):
        self._index: Dict[str, Dict[str, Set[str]]] = {}  # field -> term -> doc_ids
        self._doc_fields: Dict[str, Dict[str, Any]] = {}  # doc_id -> fields
        self._term_freq: Dict[str, Dict[str, int]] = {}  # doc_id -> term -> freq
        self._doc_freq: Dict[str, int] = {}  # term -> document count
    
    def add_document(self, doc_id: str, fields: Dict[str, Any],
                    text_fields: Optional[List[str]] = None) -> None:
        """Add document to index."""
        self._doc_fields[doc_id] = fields
        
        text_fields = text_fields or list(fields.keys())
        
        for field_name in text_fields:
            if field_name not in fields:
                continue
            
            if field_name not in self._index:
                self._index[field_name] = {}
            
            # Tokenize text
            text = str(fields[field_name])
            tokens = self._tokenize(text)
            
            # Track term frequency in document
            self._term_freq[doc_id] = self._term_freq.get(doc_id, {})
            
            for token in tokens:
                if token not in self._index[field_name]:
                    self._index[field_name][token] = set()
                    self._doc_freq[token] = 0
                
                if doc_id not in self._index[field_name][token]:
                    self._index[field_name][token].add(doc_id)
                    self._doc_freq[token] += 1
                
                self._term_freq[doc_id][token] = self._term_freq[doc_id].get(token, 0) + 1
    
    def remove_document(self, doc_id: str) -> None:
        """Remove document from index."""
        if doc_id not in self._doc_fields:
            return
        
        # Remove from term lists
        if doc_id in self._term_freq:
            for term in self._term_freq[doc_id]:
                for field_index in self._index.values():
                    if term in field_index:
                        field_index[term].discard(doc_id)
                        if not field_index[term]:
                            del field_index[term]
                
                if term in self._doc_freq:
                    self._doc_freq[term] -= 1
                    if self._doc_freq[term] <= 0:
                        del self._doc_freq[term]
            
            del self._term_freq[doc_id]
        
        del self._doc_fields[doc_id]
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """Search for documents matching query."""
        tokens = self._tokenize(query)
        
        if not tokens:
            return []
        
        fields = fields or list(self._index.keys())
        
        # Calculate scores for each document
        scores: Dict[str, float] = {}
        
        for token in tokens:
            for field_name in fields:
                if field_name not in self._index:
                    continue
                
                if token not in self._index[field_name]:
                    continue
                
                # TF-IDF scoring
                df = self._doc_freq.get(token, 0)
                n_docs = len(self._doc_fields)
                
                if df == 0 or n_docs == 0:
                    continue
                
                # IDF
                idf = math.log((n_docs + 1) / (df + 1)) + 1
                
                # Find documents with this term
                for doc_id in self._index[field_name][token]:
                    tf = self._term_freq.get(doc_id, {}).get(token, 0)
                    
                    # TF normalization
                    tf_norm = tf / (tf + 1)
                    
                    score = tf_norm * idf
                    
                    scores[doc_id] = scores.get(doc_id, 0) + score
        
        # Sort by score descending
        results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return results
    
    def get_stats(self) -> IndexStats:
        """Get index statistics."""
        total_terms = sum(
            len(terms)
            for field_terms in self._index.values()
            for terms in field_terms.values()
        )
        
        field_stats = {}
        for field_name, terms in self._index.items():
            field_stats[field_name] = {
                "unique_terms": len(terms),
                "total_occurrences": sum(len(docs) for docs in terms.values()),
            }
        
        return IndexStats(
            total_documents=len(self._doc_fields),
            total_terms=total_terms,
            field_stats=field_stats,
        )
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        # Lowercase and split on non-alphanumeric
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        
        # Remove stopwords
        stopwords = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                     'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
                     'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
                     'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
                     'below', 'between', 'under', 'again', 'further', 'then', 'once', 'and',
                     'but', 'or', 'nor', 'so', 'yet', 'both', 'either', 'neither', 'not',
                     'only', 'own', 'same', 'than', 'too', 'very', 'just', 'also'}
        
        return [t for t in tokens if t not in stopwords and len(t) > 1]
    
    def get_suggestions(self, prefix: str, field: Optional[str] = None,
                       limit: int = 10) -> List[str]:
        """Get term suggestions for prefix."""
        suggestions = set()
        
        fields = [field] if field else list(self._index.keys())
        
        for field_name in fields:
            if field_name not in self._index:
                continue
            
            for term in self._index[field_name].keys():
                if term.startswith(prefix.lower()):
                    suggestions.add(term)
                    
                    if len(suggestions) >= limit:
                        break
            
            if len(suggestions) >= limit:
                break
        
        return sorted(suggestions)[:limit]


class SearchEngine:
    """Full-text search engine."""
    
    def __init__(self):
        self._index = InvertedIndex()
        self._documents: Dict[str, Document] = {}
        self._filters: Dict[str, Dict[str, Set[str]]] = {}  # field -> value -> doc_ids
        
        # Statistics
        self._stats = {
            "total_indexed": 0,
            "total_searches": 0,
            "total_queries": 0,
        }
    
    def index_document(self, doc_id: str, fields: Dict[str, Any],
                      text_fields: Optional[List[str]] = None) -> str:
        """Index a document."""
        if doc_id in self._documents:
            self._index.remove_document(doc_id)
        
        doc = Document(doc_id=doc_id, fields=fields)
        
        self._documents[doc_id] = doc
        self._index.add_document(doc_id, fields, text_fields)
        
        # Build filter index
        for field_name, value in fields.items():
            if field_name not in self._filters:
                self._filters[field_name] = {}
            
            value_str = str(value)
            if value_str not in self._filters[field_name]:
                self._filters[field_name][value_str] = set()
            
            self._filters[field_name][value_str].add(doc_id)
        
        self._stats["total_indexed"] += 1
        
        logger.debug("Document indexed: %s", doc_id)
        
        return doc_id
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from index."""
        if doc_id not in self._documents:
            return False
        
        self._index.remove_document(doc_id)
        
        # Remove from filter index
        doc = self._documents[doc_id]
        for field_name, value in doc.fields.items():
            if field_name in self._filters:
                value_str = str(value)
                if value_str in self._filters[field_name]:
                    self._filters[field_name][value_str].discard(doc_id)
        
        del self._documents[doc_id]
        
        return True
    
    def search(self, query: str, fields: Optional[List[str]] = None,
              filters: Optional[Dict[str, Any]] = None,
              limit: int = 10,
              highlight: bool = False) -> List[SearchResult]:
        """Search for documents."""
        self._stats["total_searches"] += 1
        self._stats["total_queries"] += 1
        
        # Get matching documents from inverted index
        matches = self._index.search(query, fields)
        
        # Apply filters
        if filters:
            filtered_doc_ids = self._apply_filters(filters)
            matches = [(doc_id, score) for doc_id, score in matches if doc_id in filtered_doc_ids]
        
        # Build results
        results = []
        
        for doc_id, score in matches[:limit]:
            doc = self._documents.get(doc_id)
            
            if not doc:
                continue
            
            highlights = {}
            if highlight and query:
                highlights = self._highlight_fields(doc.fields, query, fields)
            
            result = SearchResult(
                doc_id=doc_id,
                score=score,
                fields=doc.fields,
                highlights=highlights,
            )
            
            results.append(result)
        
        return results
    
    def _apply_filters(self, filters: Dict[str, Any]) -> Set[str]:
        """Apply filters to get matching doc IDs."""
        matching_ids: Optional[Set[str]] = None
        
        for field_name, value in filters.items():
            if field_name not in self._filters:
                return set()
            
            value_str = str(value)
            if value_str not in self._filters[field_name]:
                return set()
            
            field_ids = self._filters[field_name][value_str]
            
            if matching_ids is None:
                matching_ids = field_ids.copy()
            else:
                matching_ids &= field_ids
        
        return matching_ids or set()
    
    def _highlight_fields(self, fields: Dict[str, Any], query: str,
                         field_names: Optional[List[str]]) -> Dict[str, str]:
        """Highlight matching terms in fields."""
        highlights = {}
        
        tokens = self._index._tokenize(query)
        
        fields_to_highlight = field_names or list(fields.keys())
        
        for field_name in fields_to_highlight:
            if field_name not in fields:
                continue
            
            text = str(fields[field_name])
            highlighted = text
            
            for token in tokens:
                pattern = re.compile(re.escape(token), re.IGNORECASE)
                highlighted = pattern.sub(f'<mark>{token}</mark>', highlighted)
            
            if highlighted != text:
                highlights[field_name] = highlighted
        
        return highlights
    
    def facet(self, field: str, query: Optional[str] = None,
             limit: int = 10) -> List[Tuple[str, int]]:
        """Get facet counts for a field."""
        if field not in self._filters:
            return []
        
        # If query provided, filter first
        if query:
            matches = self._index.search(query)
            match_ids = set(doc_id for doc_id, _ in matches)
        else:
            match_ids = set(self._documents.keys())
        
        # Count values
        value_counts: Dict[str, int] = {}
        
        for value, doc_ids in self._filters[field].items():
            count = len(doc_ids & match_ids)
            if count > 0:
                value_counts[value] = count
        
        # Sort by count descending
        sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_values[:limit]
    
    def suggest(self, prefix: str, field: Optional[str] = None,
               limit: int = 10) -> List[str]:
        """Get search suggestions for prefix."""
        return self._index.get_suggestions(prefix, field, limit)
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get document by ID."""
        return self._documents.get(doc_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get search statistics."""
        index_stats = self._index.get_stats()
        
        return {
            **self._stats,
            "total_documents": len(self._documents),
            "total_terms": index_stats.total_terms,
            "field_stats": index_stats.field_stats,
        }
    
    def clear(self) -> int:
        """Clear all documents from index."""
        count = len(self._documents)
        self._documents.clear()
        self._index = InvertedIndex()
        self._filters.clear()
        return count
    
    def bulk_index(self, documents: List[Dict[str, Any]],
                  doc_id_field: str = "id",
                  text_fields: Optional[List[str]] = None) -> int:
        """Index multiple documents."""
        count = 0
        
        for doc_data in documents:
            doc_id = str(doc_data.get(doc_id_field, uuid.uuid4().hex[:16]))
            fields = {k: v for k, v in doc_data.items() if k != doc_id_field}
            
            self.index_document(doc_id, fields, text_fields)
            count += 1
        
        return count


def create_search_engine() -> SearchEngine:
    """Factory function to create search engine."""
    return SearchEngine()
