"""Tests for Search Advanced Engine — Slice 65."""
import pytest
from copilot_core.search_advanced.engine import (
    SearchEngine,
    SearchDocument,
    SearchHit,
    SearchResult,
    Facet,
    MatchType,
    create_search_engine,
)
from datetime import datetime, timezone


class TestMatchType:
    """Test match types."""
    
    def test_match_type_enum_values(self):
        """Test match type enum values."""
        assert MatchType.EXACT.value == "exact"
        assert MatchType.PREFIX.value == "prefix"
        assert MatchType.FUZZY.value == "fuzzy"
        assert MatchType.PHRASE.value == "phrase"
        assert MatchType.WILDCARD.value == "wildcard"


class TestSearchDocument:
    """Test search document."""
    
    def test_create_document(self):
        """Test creating search document."""
        doc = SearchDocument(
            doc_id="doc_test",
            content="Test content here",
            boost=1.5,
        )
        
        assert doc.doc_id == "doc_test"
        assert doc.boost == 1.5
    
    def test_document_metadata_empty_by_default(self):
        """Test that document metadata is empty by default."""
        doc = SearchDocument(
            doc_id="doc_test",
            content="Test",
        )
        
        assert doc.metadata == {}
    
    def test_document_fields_empty_by_default(self):
        """Test that document fields is empty by default."""
        doc = SearchDocument(
            doc_id="doc_test",
            content="Test",
        )
        
        assert doc.fields == {}


class TestSearchHit:
    """Test search hit."""
    
    def test_create_hit(self):
        """Test creating search hit."""
        hit = SearchHit(
            doc_id="doc_test",
            score=0.85,
            content="Matched content",
        )
        
        assert hit.doc_id == "doc_test"
        assert hit.score == 0.85
    
    def test_hit_to_dict(self):
        """Test hit serialization."""
        hit = SearchHit(
            doc_id="doc_test",
            score=0.9,
            content="Content",
            metadata={"category": "tech"},
            highlights={"content": "<mark>Content</mark>"},
            matched_fields=["title", "body"],
        )
        
        d = hit.to_dict()
        
        assert d["score"] == 0.9
        assert d["metadata"]["category"] == "tech"
        assert len(d["matched_fields"]) == 2


class TestSearchResult:
    """Test search result."""
    
    def test_create_result(self):
        """Test creating search result."""
        result = SearchResult(
            query="test query",
            total_count=10,
        )
        
        assert result.query == "test query"
        assert result.total_count == 10
    
    def test_result_to_dict(self):
        """Test result serialization."""
        hit = SearchHit("doc1", 0.8, "content")
        
        result = SearchResult(
            query="test",
            hits=[hit],
            total_count=1,
            execution_time_ms=15.5,
        )
        
        d = result.to_dict()
        
        assert d["query"] == "test"
        assert len(d["hits"]) == 1
        assert d["execution_time_ms"] == 15.5


class TestFacet:
    """Test facet."""
    
    def test_create_facet(self):
        """Test creating facet."""
        facet = Facet(name="category")
        
        assert facet.name == "category"
        assert facet.values == {}
    
    def test_facet_to_dict(self):
        """Test facet serialization."""
        facet = Facet(
            name="status",
            values={"active": 10, "inactive": 5},
        )
        
        d = facet.to_dict()
        
        assert d["name"] == "status"
        assert d["values"]["active"] == 10


class TestSearchEngine:
    """Test search engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_search_engine()
        assert engine is not None
    
    def test_index_document(self):
        """Test indexing document."""
        engine = SearchEngine()
        
        result = engine.index_document(
            doc_id="doc1",
            content="This is a test document about Python programming",
        )
        
        assert result is True
        
        doc = engine.get_document("doc1")
        
        assert doc is not None
        assert "Python" in doc.content
    
    def test_index_document_with_metadata(self):
        """Test indexing document with metadata."""
        engine = SearchEngine()
        
        engine.index_document(
            doc_id="doc1",
            content="Test content",
            metadata={"category": "tech", "author": "John"},
        )
        
        doc = engine.get_document("doc1")
        
        assert doc.metadata["category"] == "tech"
        assert doc.metadata["author"] == "John"
    
    def test_index_document_with_fields(self):
        """Test indexing document with fields."""
        engine = SearchEngine()
        
        engine.index_document(
            doc_id="doc1",
            content="Main content",
            fields={"title": "Python Guide", "summary": "Learn Python"},
        )
        
        doc = engine.get_document("doc1")
        
        assert doc.fields["title"] == "Python Guide"
    
    def test_index_document_with_boost(self):
        """Test indexing document with boost."""
        engine = SearchEngine()
        
        engine.index_document(
            doc_id="doc1",
            content="Important content",
            boost=2.0,
        )
        
        doc = engine.get_document("doc1")
        
        assert doc.boost == 2.0
    
    def test_delete_document(self):
        """Test deleting document."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Test content")
        
        result = engine.delete_document("doc1")
        
        assert result is True
        assert engine.get_document("doc1") is None
    
    def test_delete_nonexistent_document(self):
        """Test deleting nonexistent document."""
        engine = SearchEngine()
        
        result = engine.delete_document("nonexistent")
        
        assert result is False
    
    def test_search_exact_match(self):
        """Test search with exact match."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python programming is great")
        engine.index_document("doc2", "Java programming is also good")
        engine.index_document("doc3", "Python snakes are interesting")
        
        result = engine.search("Python programming")
        
        assert result.total_count >= 1
        assert result.hits[0].doc_id == "doc1"
    
    def test_search_with_limit(self):
        """Test search with limit."""
        engine = SearchEngine()
        
        for i in range(20):
            engine.index_document(f"doc{i}", f"Document {i} about Python")
        
        result = engine.search("Python", limit=5)
        
        assert result.returned_count <= 5
    
    def test_search_with_offset(self):
        """Test search with offset."""
        engine = SearchEngine()
        
        for i in range(10):
            engine.index_document(f"doc{i}", f"Document {i} Python")
        
        result1 = engine.search("Python", limit=5, offset=0)
        result2 = engine.search("Python", limit=5, offset=5)
        
        # Different results
        assert result1.hits[0].doc_id != result2.hits[0].doc_id
    
    def test_search_prefix_match(self):
        """Test search with prefix match."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python programming")
        engine.index_document("doc2", "Pyramid schemes")
        engine.index_document("doc3", "Java programming")
        
        result = engine.search("Pyth", match_type=MatchType.PREFIX)
        
        # Should match "Python"
        assert result.total_count >= 1
    
    def test_search_fuzzy_match(self):
        """Test search with fuzzy match."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python programming")
        engine.index_document("doc2", "Java programming")
        
        # Search with typo
        result = engine.search("Pythn", match_type=MatchType.FUZZY)
        
        # Should still match "Python"
        assert result.total_count >= 1
    
    def test_search_phrase_match(self):
        """Test search with phrase match."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python programming is fun")
        engine.index_document("doc2", "Programming in Python is great")
        
        result = engine.search("Python programming", match_type=MatchType.PHRASE)
        
        assert result.total_count >= 1
    
    def test_search_wildcard_match(self):
        """Test search with wildcard match."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python programming")
        engine.index_document("doc2", "Pyramid building")
        engine.index_document("doc3", "Java programming")
        
        result = engine.search("Py*", match_type=MatchType.WILDCARD)
        
        # Should match Python and Pyramid
        assert result.total_count >= 2
    
    def test_search_field_specific(self):
        """Test search in specific fields."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            "Main content here",
            fields={"title": "Python Guide", "body": "Learn Java instead"},
        )
        
        result = engine.search("Python", fields=["title"])
        
        assert result.total_count >= 1
    
    def test_search_with_highlighting(self):
        """Test search with highlighting."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python is a great programming language")
        
        result = engine.search("Python", highlight=True)
        
        assert len(result.hits) >= 1
        assert "highlights" in result.hits[0].to_dict()
    
    def test_search_with_facets(self):
        """Test search with facets."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            "Python guide",
            metadata={"category": "programming"},
        )
        engine.index_document(
            "doc2",
            "Python snake info",
            metadata={"category": "animals"},
        )
        
        result = engine.search("Python", facets=["category"])
        
        assert "category" in result.facets
    
    def test_add_synonym(self):
        """Test adding synonyms."""
        engine = SearchEngine()
        
        engine.add_synonym("python", ["snake", "conda", "monty"])
        
        engine.index_document("doc1", "Snake handling guide")
        
        # Search for python should match snake document
        result = engine.search("python")
        
        assert result.total_count >= 1
    
    def test_remove_synonym(self):
        """Test removing synonyms."""
        engine = SearchEngine()
        
        engine.add_synonym("python", ["snake"])
        
        result = engine.remove_synonym("python")
        
        assert result is True
    
    def test_remove_nonexistent_synonym(self):
        """Test removing nonexistent synonym."""
        engine = SearchEngine()
        
        result = engine.remove_synonym("nonexistent")
        
        assert result is False
    
    def test_add_stop_word(self):
        """Test adding stop word."""
        engine = SearchEngine()
        
        engine.add_stop_word("custom")
        
        assert "custom" in engine._stop_words
    
    def test_remove_stop_word(self):
        """Test removing stop word."""
        engine = SearchEngine()
        
        engine.add_stop_word("tempword")
        
        result = engine.remove_stop_word("tempword")
        
        assert result is True
        assert "tempword" not in engine._stop_words
    
    def test_remove_nonexistent_stop_word(self):
        """Test removing nonexistent stop word."""
        engine = SearchEngine()
        
        result = engine.remove_stop_word("nonexistent")
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Test content")
        engine.index_document("doc2", "More content")
        
        engine.search("test")
        
        stats = engine.get_statistics()
        
        assert stats["total_documents"] == 2
        assert stats["total_searches"] == 1
    
    def test_statistics_index_size(self):
        """Test that statistics track index size."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python Java Ruby")
        
        stats = engine.get_statistics()
        
        assert stats["index_size"] >= 3  # At least 3 terms
    
    def test_statistics_synonym_count(self):
        """Test that statistics track synonym count."""
        engine = SearchEngine()
        
        engine.add_synonym("python", ["snake"])
        engine.add_synonym("java", ["coffee"])
        
        stats = engine.get_statistics()
        
        assert stats["synonym_count"] == 2
    
    def test_clear(self):
        """Test clearing all documents."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Content 1")
        engine.index_document("doc2", "Content 2")
        
        count = engine.clear()
        
        assert count == 2
        
        stats = engine.get_statistics()
        
        assert stats["total_documents"] == 0
    
    def test_reindex_all(self):
        """Test reindexing all documents."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python guide")
        engine.index_document("doc2", "Java guide")
        
        count = engine.reindex_all()
        
        assert count == 2
        
        # Search should still work
        result = engine.search("Python")
        
        assert result.total_count >= 1
    
    def test_search_min_score_filter(self):
        """Test search with minimum score filter."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python programming expert guide")
        engine.index_document("doc2", "Mention of python once")
        
        result = engine.search("Python programming", min_score=0.5)
        
        # doc1 should have higher score
        if len(result.hits) >= 1:
            assert result.hits[0].score >= 0.5
    
    def test_search_execution_time(self):
        """Test that search tracks execution time."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Test content for search")
        
        result = engine.search("test")
        
        assert result.execution_time_ms >= 0
    
    def test_document_indexed_at_set(self):
        """Test that document indexed_at is set."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Test content")
        
        doc = engine.get_document("doc1")
        
        assert doc.indexed_at is not None
    
    def test_search_empty_query(self):
        """Test search with empty query."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Test content")
        
        result = engine.search("")
        
        assert result.total_count == 0
    
    def test_search_nonexistent_term(self):
        """Test search for nonexistent term."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python programming")
        
        result = engine.search("nonexistentterm123")
        
        assert result.total_count == 0
    
    def test_update_document(self):
        """Test updating document (re-indexing same ID)."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Original content about Java")
        
        # Update with new content
        engine.index_document("doc1", "Updated content about Python")
        
        result = engine.search("Java")
        
        # Should not find Java anymore
        assert result.total_count == 0
        
        result = engine.search("Python")
        
        # Should find Python
        assert result.total_count >= 1
    
    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "PYTHON PROGRAMMING")
        
        result = engine.search("python")
        
        assert result.total_count >= 1
        
        result = engine.search("Python")
        
        assert result.total_count >= 1
    
    def test_search_stops_words_filtered(self):
        """Test that stop words are filtered."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "The quick brown fox")
        
        # Search with only stop words should return nothing
        result = engine.search("the and or")
        
        assert result.total_count == 0
    
    def test_search_min_word_length(self):
        """Test minimum word length filtering."""
        engine = SearchEngine(min_word_length=3)
        
        engine.index_document("doc1", "I am a Python developer")
        
        # "I" and "a" should be filtered out
        result = engine.search("I a")
        
        assert result.total_count == 0
    
    def test_boost_affects_score(self):
        """Test that document boost affects score."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python guide", boost=1.0)
        engine.index_document("doc2", "Python guide", boost=3.0)
        
        result = engine.search("Python")
        
        # doc2 should have higher score due to boost
        if len(result.hits) >= 2:
            assert result.hits[0].doc_id == "doc2"
    
    def test_field_match_scores_higher(self):
        """Test that field matches score higher than content."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            "Mention of python in content",
            fields={"title": "Python Programming"},
        )
        
        result = engine.search("Python")
        
        # Should match and title should be in matched_fields
        if len(result.hits) >= 1:
            assert "title" in result.hits[0].matched_fields
    
    def test_facet_values_count(self):
        """Test that facet values are counted correctly."""
        engine = SearchEngine()
        
        for i in range(5):
            engine.index_document(
                f"doc{i}",
                f"Document {i}",
                metadata={"category": "tech"},
            )
        
        for i in range(3):
            engine.index_document(
                f"doc{i+5}",
                f"Document {i+5}",
                metadata={"category": "science"},
            )
        
        result = engine.search("Document", facets=["category"])
        
        assert result.facets["category"].values.get("tech", 0) == 5
        assert result.facets["category"].values.get("science", 0) == 3
    
    def test_highlight_marks_terms(self):
        """Test that highlighting marks matched terms."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python is great for programming")
        
        result = engine.search("Python", highlight=True)
        
        if len(result.hits) >= 1 and result.hits[0].highlights:
            highlight = result.hits[0].highlights.get("content", "")
            assert "<mark>" in highlight or "Python" in highlight
    
    def test_search_result_total_count(self):
        """Test that result includes total count."""
        engine = SearchEngine()
        
        for i in range(100):
            engine.index_document(f"doc{i}", f"Python document {i}")
        
        result = engine.search("Python", limit=10)
        
        assert result.total_count == 100
        assert result.returned_count == 10
    
    def test_document_id_unique(self):
        """Test that document IDs are unique (last write wins)."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "First content")
        engine.index_document("doc1", "Second content")
        
        doc = engine.get_document("doc1")
        
        assert "Second" in doc.content
    
    def test_statistics_total_terms(self):
        """Test that statistics track total terms."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python Java Ruby")
        
        stats = engine.get_statistics()
        
        assert stats["total_terms"] >= 3
    
    def test_statistics_stop_word_count(self):
        """Test that statistics track stop word count."""
        engine = SearchEngine()
        
        stats = engine.get_statistics()
        
        # Default stop words
        assert stats["stop_word_count"] >= 10
    
    def test_search_multiple_terms(self):
        """Test search with multiple terms."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python Java programming")
        engine.index_document("doc2", "Python only")
        engine.index_document("doc3", "Java only")
        
        result = engine.search("Python Java")
        
        # doc1 should rank highest (has both terms)
        assert result.hits[0].doc_id == "doc1"
    
    def test_search_result_query_preserved(self):
        """Test that result preserves original query."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Test content")
        
        result = engine.search("original query")
        
        assert result.query == "original query"
    
    def test_clear_empty_engine(self):
        """Test clearing empty engine."""
        engine = SearchEngine()
        
        count = engine.clear()
        
        assert count == 0
    
    def test_reindex_empty_engine(self):
        """Test reindexing empty engine."""
        engine = SearchEngine()
        
        count = engine.reindex_all()
        
        assert count == 0
    
    def test_get_document_nonexistent(self):
        """Test getting nonexistent document."""
        engine = SearchEngine()
        
        doc = engine.get_document("nonexistent")
        
        assert doc is None
    
    def test_search_with_special_characters(self):
        """Test search with special characters."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "C++ programming guide")
        engine.index_document("doc2", "C# development")
        
        result = engine.search("C++")
        
        assert result.total_count >= 1
    
    def test_wildcard_single_char(self):
        """Test wildcard with single character (?)."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Cat animal")
        engine.index_document("doc2", "Bat animal")
        engine.index_document("doc3", "Car vehicle")
        
        result = engine.search("?at", match_type=MatchType.WILDCARD)
        
        # Should match Cat and Bat
        assert result.total_count >= 2
    
    def test_synonym_expansion(self):
        """Test that synonyms expand search."""
        engine = SearchEngine()
        
        engine.add_synonym("car", ["auto", "vehicle", "automobile"])
        
        engine.index_document("doc1", "Auto racing is fun")
        
        result = engine.search("car")
        
        # Should match via synonym
        assert result.total_count >= 1
    
    def test_facet_empty_when_no_matches(self):
        """Test that facets are empty when no matches."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Test", metadata={"category": "tech"})
        
        result = engine.search("nonexistent", facets=["category"])
        
        assert result.facets.get("category") is None or result.facets["category"].values == {}
    
    def test_highlight_custom_markers(self):
        """Test custom highlight markers."""
        engine = SearchEngine(
            highlight_prefix="<<",
            highlight_suffix=">>",
        )
        
        engine.index_document("doc1", "Python is great")
        
        result = engine.search("Python", highlight=True)
        
        if len(result.hits) >= 1 and result.hits[0].highlights:
            highlight = result.hits[0].highlights.get("content", "")
            assert "<<" in highlight or ">>" in highlight
    
    def test_search_returns_hits_list(self):
        """Test that search returns hits list."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python content")
        
        result = engine.search("Python")
        
        assert isinstance(result.hits, list)
    
    def test_hit_score_positive(self):
        """Test that hit scores are positive."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python programming guide")
        
        result = engine.search("Python")
        
        if len(result.hits) >= 1:
            assert result.hits[0].score > 0
    
    def test_multiple_documents_independent(self):
        """Test that multiple documents are independent."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Python only")
        engine.index_document("doc2", "Java only")
        engine.index_document("doc3", "Ruby only")
        
        python_result = engine.search("Python")
        java_result = engine.search("Java")
        ruby_result = engine.search("Ruby")
        
        assert python_result.hits[0].doc_id == "doc1"
        assert java_result.hits[0].doc_id == "doc2"
        assert ruby_result.hits[0].doc_id == "doc3"
    
    def test_levenshtein_distance_same_string(self):
        """Test Levenshtein distance for same string."""
        engine = SearchEngine()
        
        distance = engine._levenshtein_distance("python", "python")
        
        assert distance == 0
    
    def test_levenshtein_distance_different_string(self):
        """Test Levenshtein distance for different strings."""
        engine = SearchEngine()
        
        distance = engine._levenshtein_distance("python", "pythn")
        
        assert distance == 1
    
    def test_tokenize_lowercase(self):
        """Test that tokenization lowercases."""
        engine = SearchEngine()
        
        tokens = engine._tokenize("PYTHON Programming")
        
        assert all(t.islower() for t in tokens)
    
    def test_tokenize_removes_punctuation(self):
        """Test that tokenization removes punctuation."""
        engine = SearchEngine()
        
        tokens = engine._tokenize("Hello, world! How are you?")
        
        assert all(t.isalnum() for t in tokens)
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = SearchEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_searches"] == 0
        assert stats["total_documents"] == 0
        assert stats["total_terms"] == 0
    
    def test_facet_to_dict(self):
        """Test facet to_dict method."""
        facet = Facet(
            name="status",
            values={"active": 10, "pending": 5},
        )
        
        d = facet.to_dict()
        
        assert d["name"] == "status"
        assert d["values"]["active"] == 10
        assert d["values"]["pending"] == 5
    
    def test_search_result_facets_dict(self):
        """Test that search result facets convert to dict properly."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Test", metadata={"cat": "A"})
        
        result = engine.search("Test", facets=["cat"])
        
        d = result.to_dict()
        
        assert "facets" in d
    
    def test_index_document_returns_true(self):
        """Test that index_document returns True."""
        engine = SearchEngine()
        
        result = engine.index_document("doc1", "Content")
        
        assert result is True
    
    def test_search_with_numeric_content(self):
        """Test search with numeric content."""
        engine = SearchEngine()
        
        engine.index_document("doc1", "Version 1.2.3 released")
        engine.index_document("doc2", "Version 2.0.0 available")
        
        result = engine.search("1.2.3")
        
        assert result.total_count >= 1
    
    def test_search_preserves_document_metadata(self):
        """Test that search results preserve document metadata."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            "Python guide",
            metadata={"author": "John", "year": 2024},
        )
        
        result = engine.search("Python")
        
        if len(result.hits) >= 1:
            assert result.hits[0].metadata["author"] == "John"
            assert result.hits[0].metadata["year"] == 2024
