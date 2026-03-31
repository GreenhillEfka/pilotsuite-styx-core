"""Search Advanced Engine — Slice 65.

Advanced search engine for PilotSuite Core.

Features:
- Full-text search with tokenization
- Fuzzy matching
- Phrase search
- Boosting and scoring
- Faceted search
- Highlighting
- Synonym support
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import uuid
import math

logger = logging.getLogger(__name__)


class MatchType(Enum):
    """Match types for search."""
    EXACT = "exact"
    PREFIX = "prefix"
    FUZZY = "fuzzy"
    PHRASE = "phrase"
    WILDCARD = "wildcard"


@dataclass
class SearchDocument:
    """Searchable document."""
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    fields: Dict[str, str] = field(default_factory=dict)
    boost: float = 1.0
    indexed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SearchHit:
    """Search result hit."""
    doc_id: str
    score: float
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    highlights: Dict[str, str] = field(default_factory=dict)
    matched_fields: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "score": self.score,
            "content": self.content,
            "metadata": self.metadata,
            "highlights": self.highlights,
            "matched_fields": self.matched_fields,
        }


@dataclass
class Facet:
    """Search facet."""
    name: str
    values: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "values": self.values,
        }


@dataclass
class SearchResult:
    """Search result."""
    query: str
    hits: List[SearchHit] = field(default_factory=list)
    total_count: int = 0
    facets: Dict[str, Facet] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "hits": [h.to_dict() for h in self.hits],
            "total_count": self.total_count,
            "facets": {k: v.to_dict() for k, v in self.facets.items()},
            "execution_time_ms": self.execution_time_ms,
        }


class SearchEngine:
    """Advanced search engine."""
    
    def __init__(self, min_word_length: int = 2,
                 fuzzy_distance: int = 2,
                 highlight_prefix: str = "<mark>",
                 highlight_suffix: str = "</mark>"):
        self._documents: Dict[str, SearchDocument] = {}
        self._index: Dict[str, Set[str]] = {}  # term -> doc_ids
        self._field_index: Dict[str, Dict[str, Set[str]]] = {}  # field -> term -> doc_ids
        self._synonyms: Dict[str, List[str]] = {}
        self._stop_words: Set[str] = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for"}
        self._lock = threading.Lock()
        
        self._min_word_length = min_word_length
        self._fuzzy_distance = fuzzy_distance
        self._highlight_prefix = highlight_prefix
        self._highlight_suffix = highlight_suffix
        
        # Statistics
        self._stats = {
            "total_searches": 0,
            "total_documents": 0,
            "total_terms": 0,
        }
    
    def index_document(self, doc_id: str, content: str,
                      metadata: Optional[Dict[str, Any]] = None,
                      fields: Optional[Dict[str, str]] = None,
                      boost: float = 1.0) -> bool:
        """Index a document for search."""
        doc = SearchDocument(
            doc_id=doc_id,
            content=content,
            metadata=metadata or {},
            fields=fields or {},
            boost=boost,
        )
        
        with self._lock:
            # Remove existing document if present
            if doc_id in self._documents:
                self._remove_from_index(doc_id)
            
            self._documents[doc_id] = doc
            
            # Index content
            self._index_text(doc_id, content, "_content")
            
            # Index fields
            for field_name, field_value in doc.fields.items():
                self._index_text(doc_id, field_value, field_name)
            
            self._stats["total_documents"] = len(self._documents)
            self._stats["total_terms"] = len(self._index)
        
        logger.debug("Document indexed: %s", doc_id)
        
        return True
    
    def _index_text(self, doc_id: str, text: str, field_name: str) -> None:
        """Index text content."""
        terms = self._tokenize(text)
        
        for term in terms:
            # Add to global index
            if term not in self._index:
                self._index[term] = set()
            self._index[term].add(doc_id)
            
            # Add to field index
            if field_name not in self._field_index:
                self._field_index[field_name] = {}
            if term not in self._field_index[field_name]:
                self._field_index[field_name][term] = set()
            self._field_index[field_name][term].add(doc_id)
    
    def _remove_from_index(self, doc_id: str) -> None:
        """Remove document from index."""
        if doc_id not in self._documents:
            return
        
        # Remove from global index
        for term in list(self._index.keys()):
            self._index[term].discard(doc_id)
            if not self._index[term]:
                del self._index[term]
        
        # Remove from field index
        for field_name in list(self._field_index.keys()):
            for term in list(self._field_index[field_name].keys()):
                self._field_index[field_name][term].discard(doc_id)
                if not self._field_index[field_name][term]:
                    del self._field_index[field_name][term]
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the index."""
        with self._lock:
            if doc_id not in self._documents:
                return False
            
            self._remove_from_index(doc_id)
            del self._documents[doc_id]
            
            self._stats["total_documents"] = len(self._documents)
        
        return True
    
    def search(self, query: str,
               limit: int = 10,
               offset: int = 0,
               fields: Optional[List[str]] = None,
               match_type: MatchType = MatchType.EXACT,
               fuzzy_distance: Optional[int] = None,
               min_score: float = 0.1,
               highlight: bool = True,
               facets: Optional[List[str]] = None) -> SearchResult:
        """Execute search query."""
        import time
        start = time.time()
        
        with self._lock:
            # Parse query
            terms = self._tokenize(query)
            
            # Expand with synonyms
            expanded_terms = self._expand_synonyms(terms)
            
            # Find matching documents
            doc_scores: Dict[str, float] = {}
            doc_matched_fields: Dict[str, List[str]] = {}
            
            for term in expanded_terms:
                matches = self._find_matches(term, match_type, fuzzy_distance)
                
                for doc_id, score, matched_field in matches:
                    if fields and matched_field not in fields and matched_field != "_content":
                        continue
                    
                    if doc_id not in doc_scores:
                        doc_scores[doc_id] = 0
                        doc_matched_fields[doc_id] = []
                    
                    doc_scores[doc_id] += score
                    if matched_field not in doc_matched_fields[doc_id]:
                        doc_matched_fields[doc_id].append(matched_field)
            
            # Apply document boosts
            for doc_id in doc_scores:
                if doc_id in self._documents:
                    doc_scores[doc_id] *= self._documents[doc_id].boost
            
            # Filter by min_score
            filtered = [(doc_id, score) for doc_id, score in doc_scores.items() if score >= min_score]
            
            # Sort by score descending
            filtered.sort(key=lambda x: x[1], reverse=True)
            
            # Apply pagination
            paginated = filtered[offset:offset + limit]
            
            # Build hits
            hits = []
            for doc_id, score in paginated:
                doc = self._documents.get(doc_id)
                if not doc:
                    continue
                
                highlights = {}
                if highlight:
                    highlights = self._highlight_matches(doc, terms)
                
                hit = SearchHit(
                    doc_id=doc_id,
                    score=score,
                    content=doc.content[:500],  # Truncate for results
                    metadata=doc.metadata,
                    highlights=highlights,
                    matched_fields=doc_matched_fields.get(doc_id, []),
                )
                hits.append(hit)
            
            # Calculate facets
            facet_results = {}
            if facets:
                facet_results = self._calculate_facets(hits, facets)
            
            execution_time = (time.time() - start) * 1000
            
            result = SearchResult(
                query=query,
                hits=hits,
                total_count=len(filtered),
                facets=facet_results,
                execution_time_ms=execution_time,
            )
            
            self._stats["total_searches"] += 1
        
        return result
    
    def _find_matches(self, term: str, match_type: MatchType,
                     fuzzy_distance: Optional[int] = None) -> List[Tuple[str, float, str]]:
        """Find documents matching term."""
        results = []
        distance = fuzzy_distance or self._fuzzy_distance
        
        if match_type == MatchType.EXACT:
            # Exact match in global index
            for doc_id in self._index.get(term, set()):
                results.append((doc_id, 1.0, "_content"))
            
            # Exact match in field index
            for field_name, field_terms in self._field_index.items():
                for doc_id in field_terms.get(term, set()):
                    results.append((doc_id, 1.5, field_name))  # Field matches score higher
        
        elif match_type == MatchType.PREFIX:
            # Prefix match
            for indexed_term in self._index:
                if indexed_term.startswith(term):
                    for doc_id in self._index[indexed_term]:
                        results.append((doc_id, 0.8, "_content"))
            
            for field_name, field_terms in self._field_index.items():
                for indexed_term in field_terms:
                    if indexed_term.startswith(term):
                        for doc_id in field_terms[indexed_term]:
                            results.append((doc_id, 1.2, field_name))
        
        elif match_type == MatchType.FUZZY:
            # Fuzzy match using Levenshtein distance
            for indexed_term in self._index:
                if self._levenshtein_distance(term, indexed_term) <= distance:
                    for doc_id in self._index[indexed_term]:
                        results.append((doc_id, 0.7, "_content"))
            
            for field_name, field_terms in self._field_index.items():
                for indexed_term in field_terms:
                    if self._levenshtein_distance(term, indexed_term) <= distance:
                        for doc_id in field_terms[indexed_term]:
                            results.append((doc_id, 1.0, field_name))
        
        elif match_type == MatchType.PHRASE:
            # Phrase search - simplified implementation
            for doc_id, doc in self._documents.items():
                if term.lower() in doc.content.lower():
                    results.append((doc_id, 1.5, "_content"))
                for field_name, field_value in doc.fields.items():
                    if term.lower() in field_value.lower():
                        results.append((doc_id, 2.0, field_name))
        
        elif match_type == MatchType.WILDCARD:
            # Wildcard match (* and ?)
            pattern = term.replace("*", ".*").replace("?", ".")
            regex = re.compile(f"^{pattern}$", re.IGNORECASE)
            
            for indexed_term in self._index:
                if regex.match(indexed_term):
                    for doc_id in self._index[indexed_term]:
                        results.append((doc_id, 0.9, "_content"))
            
            for field_name, field_terms in self._field_index.items():
                for indexed_term in field_terms:
                    if regex.match(indexed_term):
                        for doc_id in field_terms[indexed_term]:
                            results.append((doc_id, 1.3, field_name))
        
        return results
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        # Convert to lowercase
        text = text.lower()
        
        # Split on non-alphanumeric
        tokens = re.split(r'[^a-z0-9]+', text)
        
        # Filter by min length and stop words
        tokens = [
            t for t in tokens
            if len(t) >= self._min_word_length and t not in self._stop_words
        ]
        
        return tokens
    
    def _expand_synonyms(self, terms: List[str]) -> List[str]:
        """Expand terms with synonyms."""
        expanded = list(terms)
        
        for term in terms:
            if term in self._synonyms:
                expanded.extend(self._synonyms[term])
        
        return expanded
    
    def _highlight_matches(self, doc: SearchDocument, terms: List[str]) -> Dict[str, str]:
        """Generate highlights for matched terms."""
        highlights = {}
        
        # Highlight content
        highlighted_content = doc.content
        for term in terms:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            highlighted_content = pattern.sub(
                f"{self._highlight_prefix}\\g<0>{self._highlight_suffix}",
                highlighted_content,
            )
        
        if highlighted_content != doc.content:
            highlights["content"] = highlighted_content[:500]
        
        # Highlight fields
        for field_name, field_value in doc.fields.items():
            highlighted_field = field_value
            for term in terms:
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                highlighted_field = pattern.sub(
                    f"{self._highlight_prefix}\\g<0>{self._highlight_suffix}",
                    highlighted_field,
                )
            
            if highlighted_field != field_value:
                highlights[field_name] = highlighted_field[:200]
        
        return highlights
    
    def _calculate_facets(self, hits: List[SearchHit],
                         facet_fields: List[str]) -> Dict[str, Facet]:
        """Calculate facets from search results."""
        facets = {}
        
        for field_name in facet_fields:
            facet = Facet(name=field_name)
            
            for hit in hits:
                # Check metadata for facet value
                if field_name in hit.metadata:
                    value = str(hit.metadata[field_name])
                    facet.values[value] = facet.values.get(value, 0) + 1
                
                # Check document fields
                if field_name in self._documents[hit.doc_id].fields:
                    value = self._documents[hit.doc_id].fields[field_name]
                    facet.values[value] = facet.values.get(value, 0) + 1
            
            facets[field_name] = facet
        
        return facets
    
    def add_synonym(self, term: str, synonyms: List[str]) -> None:
        """Add synonyms for a term."""
        with self._lock:
            self._synonyms[term] = synonyms
    
    def remove_synonym(self, term: str) -> bool:
        """Remove synonyms for a term."""
        with self._lock:
            if term in self._synonyms:
                del self._synonyms[term]
                return True
            return False
    
    def add_stop_word(self, word: str) -> None:
        """Add a stop word."""
        with self._lock:
            self._stop_words.add(word)
    
    def remove_stop_word(self, word: str) -> bool:
        """Remove a stop word."""
        with self._lock:
            if word in self._stop_words:
                self._stop_words.remove(word)
                return True
            return False
    
    def get_document(self, doc_id: str) -> Optional[SearchDocument]:
        """Get document by ID."""
        return self._documents.get(doc_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get search engine statistics."""
        with self._lock:
            return {
                **self._stats,
                "index_size": len(self._index),
                "synonym_count": len(self._synonyms),
                "stop_word_count": len(self._stop_words),
            }
    
    def clear(self) -> int:
        """Clear all documents and index."""
        with self._lock:
            count = len(self._documents)
            self._documents.clear()
            self._index.clear()
            self._field_index.clear()
            self._stats["total_documents"] = 0
            self._stats["total_terms"] = 0
            return count
    
    def reindex_all(self) -> int:
        """Reindex all documents."""
        with self._lock:
            # Clear index
            self._index.clear()
            self._field_index.clear()
            
            # Reindex all documents
            for doc_id, doc in self._documents.items():
                self._index_text(doc_id, doc.content, "_content")
                for field_name, field_value in doc.fields.items():
                    self._index_text(doc_id, field_value, field_name)
            
            self._stats["total_terms"] = len(self._index)
            
            return len(self._documents)


def create_search_engine(**kwargs) -> SearchEngine:
    """Factory function to create search engine."""
    return SearchEngine(**kwargs)
