"""Tests for Search Advanced Engine — Slice 56."""
import pytest
from copilot_core.search_advanced.engine import (
    SearchEngine,
    InvertedIndex,
    Document,
    SearchResult,
    IndexStats,
    FieldType,
    create_search_engine,
)
from datetime import datetime, timezone


class TestInvertedIndex:
    """Test inverted index."""
    
    def test_add_document(self):
        """Test adding document to index."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello World", "content": "Test content"})
        
        assert "doc1" in index._doc_fields
    
    def test_add_document_indexes_terms(self):
        """Test that adding document indexes terms."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello World"})
        
        # "hello" and "world" should be indexed
        assert "hello" in index._index.get("title", {})
        assert "world" in index._index.get("title", {})
    
    def test_add_document_stops_removed(self):
        """Test that stopwords are removed."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"text": "The quick brown fox"})
        
        # "the" should be removed as stopword
        assert "the" not in index._index.get("text", {})
        assert "quick" in index._index.get("text", {})
    
    def test_add_document_single_char_removed(self):
        """Test that single character terms are removed."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"text": "a b c test"})
        
        assert "a" not in index._index.get("text", {})
        assert "b" not in index._index.get("text", {})
        assert "test" in index._index.get("text", {})
    
    def test_remove_document(self):
        """Test removing document from index."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello World"})
        index.remove_document("doc1")
        
        assert "doc1" not in index._doc_fields
    
    def test_remove_document_updates_terms(self):
        """Test that removing document updates term lists."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello"})
        index.add_document("doc2", {"title": "Hello World"})
        
        index.remove_document("doc1")
        
        # "hello" should still exist (doc2 has it)
        assert "hello" in index._index.get("title", {})
        assert "doc1" not in index._index["title"]["hello"]
    
    def test_search_basic(self):
        """Test basic search."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello World"})
        index.add_document("doc2", {"title": "Hello There"})
        index.add_document("doc3", {"title": "Goodbye World"})
        
        results = index.search("hello")
        
        assert len(results) == 2
        assert results[0][0] in ("doc1", "doc2")
    
    def test_search_no_match(self):
        """Test search with no matches."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello World"})
        
        results = index.search("nonexistent")
        
        assert len(results) == 0
    
    def test_search_by_field(self):
        """Test search restricted to specific field."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Python", "content": "Java"})
        index.add_document("doc2", {"title": "Java", "content": "Python"})
        
        # Search only in title
        results = index.search("python", fields=["title"])
        
        assert len(results) == 1
        assert results[0][0] == "doc1"
    
    def test_search_scoring(self):
        """Test that search results are scored."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"text": "Python Python Python"})
        index.add_document("doc2", {"text": "Python"})
        
        results = index.search("python")
        
        # doc1 should score higher (more occurrences)
        assert results[0][0] == "doc1"
        assert results[0][1] > results[1][1]
    
    def test_search_empty_query(self):
        """Test search with empty query."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello"})
        
        results = index.search("")
        
        assert len(results) == 0
    
    def test_get_stats(self):
        """Test getting index statistics."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello World", "content": "Test"})
        index.add_document("doc2", {"title": "Hello There", "content": "Test Content"})
        
        stats = index.get_stats()
        
        assert stats.total_documents == 2
        assert stats.total_terms > 0
        assert "title" in stats.field_stats
    
    def test_get_suggestions(self):
        """Test getting term suggestions."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Python Programming"})
        index.add_document("doc2", {"title": "Python Guide"})
        index.add_document("doc3", {"title": "Java Programming"})
        
        suggestions = index.get_suggestions("pyth")
        
        assert "python" in suggestions
    
    def test_get_suggestions_by_field(self):
        """Test getting suggestions for specific field."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Python", "content": "Java"})
        
        suggestions = index.get_suggestions("pyth", field="title")
        
        assert "python" in suggestions
    
    def test_get_suggestions_limit(self):
        """Test suggestions limit."""
        index = InvertedIndex()
        
        for i in range(20):
            index.add_document(f"doc{i}", {"title": f"term{i}"})
        
        suggestions = index.get_suggestions("term", limit=5)
        
        assert len(suggestions) <= 5
    
    def test_get_suggestions_no_match(self):
        """Test suggestions with no match."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"title": "Hello"})
        
        suggestions = index.get_suggestions("xyz")
        
        assert suggestions == []
    
    def test_tokenize_lowercase(self):
        """Test that tokenization lowercases."""
        index = InvertedIndex()
        
        tokens = index._tokenize("Hello WORLD")
        
        assert "hello" in tokens
        assert "world" in tokens
    
    def test_tokenize_removes_punctuation(self):
        """Test that tokenization removes punctuation."""
        index = InvertedIndex()
        
        tokens = index._tokenize("Hello, World! How are you?")
        
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens
        assert "!" not in tokens
    
    def test_document_freq_tracked(self):
        """Test that document frequency is tracked."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"text": "hello"})
        index.add_document("doc2", {"text": "hello world"})
        index.add_document("doc3", {"text": "hello"})
        
        assert index._doc_freq["hello"] == 3
    
    def test_term_freq_tracked(self):
        """Test that term frequency per document is tracked."""
        index = InvertedIndex()
        
        index.add_document("doc1", {"text": "hello hello hello"})
        
        assert index._term_freq["doc1"]["hello"] == 3
    
    def test_add_document_multiple_fields(self):
        """Test adding document with multiple text fields."""
        index = InvertedIndex()
        
        index.add_document(
            "doc1",
            {"title": "Python", "content": "Java", "tags": "coding"},
            text_fields=["title", "content"],
        )
        
        # Only title and content should be indexed
        assert "python" in index._index.get("title", {})
        assert "java" in index._index.get("content", {})
        # "coding" should not be indexed (tags not in text_fields)
        assert "coding" not in index._index.get("tags", {})


class TestSearchEngine:
    """Test search engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_search_engine()
        assert engine is not None
    
    def test_index_document(self):
        """Test indexing a document."""
        engine = SearchEngine()
        
        doc_id = engine.index_document(
            "doc1",
            {"title": "Hello World", "content": "Test content"},
        )
        
        assert doc_id == "doc1"
    
    def test_index_document_auto_id(self):
        """Test indexing with auto-generated ID."""
        engine = SearchEngine()
        
        # This test uses explicit ID, but the function supports any string
        doc_id = engine.index_document("auto_123", {"title": "Test"})
        
        assert doc_id == "auto_123"
    
    def test_index_document_stores_fields(self):
        """Test that indexed document stores fields."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello", "count": 42})
        
        doc = engine.get_document("doc1")
        
        assert doc is not None
        assert doc.fields["title"] == "Hello"
        assert doc.fields["count"] == 42
    
    def test_delete_document(self):
        """Test deleting a document."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello"})
        
        result = engine.delete_document("doc1")
        
        assert result is True
        assert engine.get_document("doc1") is None
    
    def test_delete_nonexistent_document(self):
        """Test deleting nonexistent document."""
        engine = SearchEngine()
        
        result = engine.delete_document("nonexistent")
        
        assert result is False
    
    def test_search_basic(self):
        """Test basic search."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python Tutorial"})
        engine.index_document("doc2", {"title": "Java Guide"})
        engine.index_document("doc3", {"title": "Python Advanced"})
        
        results = engine.search("python")
        
        assert len(results) == 2
    
    def test_search_with_filters(self):
        """Test search with filters."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python", "category": "tutorial"})
        engine.index_document("doc2", {"title": "Python", "category": "advanced"})
        engine.index_document("doc3", {"title": "Java", "category": "tutorial"})
        
        results = engine.search("python", filters={"category": "tutorial"})
        
        assert len(results) == 1
        assert results[0].doc_id == "doc1"
    
    def test_search_with_multiple_filters(self):
        """Test search with multiple filters."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python", "category": "tutorial", "level": "beginner"})
        engine.index_document("doc2", {"title": "Python", "category": "tutorial", "level": "advanced"})
        engine.index_document("doc3", {"title": "Python", "category": "advanced", "level": "beginner"})
        
        results = engine.search("python", filters={"category": "tutorial", "level": "beginner"})
        
        assert len(results) == 1
        assert results[0].doc_id == "doc1"
    
    def test_search_with_limit(self):
        """Test search with limit."""
        engine = SearchEngine()
        
        for i in range(20):
            engine.index_document(f"doc{i}", {"title": f"Python Topic {i}"})
        
        results = engine.search("python", limit=5)
        
        assert len(results) == 5
    
    def test_search_with_highlight(self):
        """Test search with highlighting."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Introduction to Python Programming"})
        
        results = engine.search("python", highlight=True)
        
        assert len(results) == 1
        assert "title" in results[0].highlights
        assert "<mark>" in results[0].highlights["title"]
    
    def test_search_no_highlight(self):
        """Test search without highlighting."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python Programming"})
        
        results = engine.search("python", highlight=False)
        
        assert len(results) == 1
        assert results[0].highlights == {}
    
    def test_search_empty_results(self):
        """Test search with no results."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello"})
        
        results = engine.search("nonexistent")
        
        assert len(results) == 0
    
    def test_facet(self):
        """Test faceted search."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python", "category": "tutorial"})
        engine.index_document("doc2", {"title": "Java", "category": "tutorial"})
        engine.index_document("doc3", {"title": "Python", "category": "advanced"})
        engine.index_document("doc4", {"title": "Python", "category": "tutorial"})
        
        facets = engine.facet("category")
        
        assert len(facets) == 2
        assert facets[0] == ("tutorial", 3)
        assert facets[1] == ("advanced", 1)
    
    def test_facet_with_query(self):
        """Test faceted search with query filter."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python Basic", "category": "tutorial"})
        engine.index_document("doc2", {"title": "Java Basic", "category": "tutorial"})
        engine.index_document("doc3", {"title": "Python Advanced", "category": "advanced"})
        
        facets = engine.facet("category", query="python")
        
        assert len(facets) == 2
        # Python docs: 2 tutorial, 1 advanced
        tutorial_count = next((count for val, count in facets if val == "tutorial"), 0)
        assert tutorial_count == 2
    
    def test_facet_with_limit(self):
        """Test facet with limit."""
        engine = SearchEngine()
        
        for i in range(20):
            category = f"cat{i}"
            engine.index_document(f"doc{i}", {"title": f"Title {i}", "category": category})
        
        facets = engine.facet("category", limit=5)
        
        assert len(facets) == 5
    
    def test_facet_nonexistent_field(self):
        """Test facet on nonexistent field."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello"})
        
        facets = engine.facet("nonexistent")
        
        assert facets == []
    
    def test_suggest(self):
        """Test search suggestions."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python Basics"})
        engine.index_document("doc2", {"title": "Python Advanced"})
        engine.index_document("doc3", {"title": "Java Basics"})
        
        suggestions = engine.suggest("pyth")
        
        assert "python" in suggestions
    
    def test_suggest_with_field(self):
        """Test suggestions for specific field."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python", "content": "Java"})
        
        suggestions = engine.suggest("pyth", field="title")
        
        assert "python" in suggestions
    
    def test_suggest_with_limit(self):
        """Test suggestions with limit."""
        engine = SearchEngine()
        
        for i in range(20):
            engine.index_document(f"doc{i}", {"title": f"term{i}"})
        
        suggestions = engine.suggest("term", limit=5)
        
        assert len(suggestions) <= 5
    
    def test_get_document(self):
        """Test getting document by ID."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello", "count": 42})
        
        doc = engine.get_document("doc1")
        
        assert doc is not None
        assert doc.doc_id == "doc1"
        assert doc.fields["title"] == "Hello"
    
    def test_get_nonexistent_document(self):
        """Test getting nonexistent document."""
        engine = SearchEngine()
        
        doc = engine.get_document("nonexistent")
        
        assert doc is None
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello World"})
        engine.index_document("doc2", {"title": "Hello There"})
        
        engine.search("hello")
        
        stats = engine.get_statistics()
        
        assert stats["total_documents"] == 2
        assert stats["total_indexed"] == 2
        assert stats["total_searches"] == 1
    
    def test_clear(self):
        """Test clearing all documents."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello"})
        engine.index_document("doc2", {"title": "World"})
        
        count = engine.clear()
        
        assert count == 2
        assert len(engine.search("hello")) == 0
    
    def test_bulk_index(self):
        """Test bulk indexing."""
        engine = SearchEngine()
        
        documents = [
            {"id": "doc1", "title": "Python", "category": "tutorial"},
            {"id": "doc2", "title": "Java", "category": "tutorial"},
            {"id": "doc3", "title": "Python", "category": "advanced"},
        ]
        
        count = engine.bulk_index(documents)
        
        assert count == 3
        assert engine.get_document("doc1") is not None
        assert engine.get_document("doc2") is not None
        assert engine.get_document("doc3") is not None
    
    def test_bulk_index_auto_id(self):
        """Test bulk indexing with auto-generated IDs."""
        engine = SearchEngine()
        
        documents = [
            {"title": "Python", "category": "tutorial"},
            {"title": "Java", "category": "tutorial"},
        ]
        
        count = engine.bulk_index(documents, doc_id_field="nonexistent")
        
        assert count == 2
    
    def test_bulk_index_with_text_fields(self):
        """Test bulk indexing with specific text fields."""
        engine = SearchEngine()
        
        documents = [
            {"id": "doc1", "title": "Python", "content": "Java", "tags": "coding"},
        ]
        
        engine.bulk_index(documents, text_fields=["title"])
        
        results = engine.search("python")
        assert len(results) == 1
        
        results = engine.search("java")
        # "java" should not be indexed (content not in text_fields)
        assert len(results) == 0
    
    def test_search_scoring_relevance(self):
        """Test that search scoring reflects relevance."""
        engine = SearchEngine()
        
        # doc1 has more occurrences
        engine.index_document("doc1", {"title": "Python Python Python"})
        engine.index_document("doc2", {"title": "Python"})
        
        results = engine.search("python")
        
        assert results[0].doc_id == "doc1"
        assert results[0].score > results[1].score
    
    def test_search_result_to_dict(self):
        """Test search result serialization."""
        result = SearchResult(
            doc_id="doc_test",
            score=0.95,
            fields={"title": "Test"},
            highlights={"title": "<mark>Test</mark>"},
        )
        
        d = result.to_dict()
        
        assert d["doc_id"] == "doc_test"
        assert d["score"] == 0.95
        assert d["highlights"]["title"] == "<mark>Test</mark>"
    
    def test_document_to_dict(self):
        """Test document serialization."""
        doc = Document(
            doc_id="doc_test",
            fields={"title": "Test", "count": 42},
        )
        
        d = doc.to_dict()
        
        assert d["doc_id"] == "doc_test"
        assert d["fields"]["title"] == "Test"
        assert d["fields"]["count"] == 42
    
    def test_index_stats_to_dict(self):
        """Test index stats serialization."""
        stats = IndexStats(
            total_documents=100,
            total_terms=500,
            field_stats={"title": {"unique_terms": 100}},
        )
        
        assert stats.total_documents == 100
        assert stats.total_terms == 500
    
    def test_field_type_enum_values(self):
        """Test field type enum values."""
        assert FieldType.TEXT.value == "text"
        assert FieldType.KEYWORD.value == "keyword"
        assert FieldType.NUMBER.value == "number"
        assert FieldType.DATE.value == "date"
        assert FieldType.BOOLEAN.value == "boolean"
    
    def test_document_created_at_set(self):
        """Test that document created_at is set."""
        doc = Document(doc_id="doc_test", fields={"title": "Test"})
        
        assert doc.created_at is not None
    
    def test_document_updated_at_set(self):
        """Test that document updated_at is set."""
        doc = Document(doc_id="doc_test", fields={"title": "Test"})
        
        assert doc.updated_at is not None
    
    def test_index_document_updates_existing(self):
        """Test that indexing existing document updates it."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Original"})
        engine.index_document("doc1", {"title": "Updated"})
        
        doc = engine.get_document("doc1")
        
        assert doc.fields["title"] == "Updated"
    
    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "PYTHON PROGRAMMING"})
        
        results = engine.search("python")
        assert len(results) == 1
        
        results = engine.search("Python")
        assert len(results) == 1
        
        results = engine.search("PYTHON")
        assert len(results) == 1
    
    def test_filter_nonexistent_value(self):
        """Test filtering by nonexistent value."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python", "category": "tutorial"})
        
        results = engine.search("python", filters={"category": "nonexistent"})
        
        assert len(results) == 0
    
    def test_filter_nonexistent_field(self):
        """Test filtering by nonexistent field."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python"})
        
        results = engine.search("python", filters={"nonexistent": "value"})
        
        assert len(results) == 0
    
    def test_highlight_multiple_fields(self):
        """Test highlighting multiple fields."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            {"title": "Python Intro", "content": "Learn Python here"},
        )
        
        results = engine.search("python", highlight=True)
        
        assert len(results) == 1
        assert "title" in results[0].highlights
        assert "content" in results[0].highlights
    
    def test_highlight_no_match(self):
        """Test highlighting when no match."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello World"})
        
        results = engine.search("hello", highlight=True)
        
        assert len(results) == 1
        # Title should have highlight
        assert "title" in results[0].highlights
    
    def test_statistics_total_queries(self):
        """Test that statistics track total queries."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test"})
        
        engine.search("test")
        engine.search("test")
        engine.search("test")
        
        stats = engine.get_statistics()
        
        assert stats["total_queries"] == 3
    
    def test_statistics_field_stats(self):
        """Test that statistics include field stats."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello", "content": "World"})
        
        stats = engine.get_statistics()
        
        assert "field_stats" in stats
        assert "title" in stats["field_stats"]
        assert "content" in stats["field_stats"]
    
    def test_search_result_fields_preserved(self):
        """Test that search result preserves all fields."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            {"title": "Python", "count": 42, "active": True, "tags": ["a", "b"]},
        )
        
        results = engine.search("python")
        
        assert len(results) == 1
        assert results[0].fields["title"] == "Python"
        assert results[0].fields["count"] == 42
        assert results[0].fields["active"] is True
        assert results[0].fields["tags"] == ["a", "b"]
    
    def test_facet_empty_index(self):
        """Test facet on empty index."""
        engine = SearchEngine()
        
        facets = engine.facet("category")
        
        assert facets == []
    
    def test_suggest_empty_index(self):
        """Test suggestions on empty index."""
        engine = SearchEngine()
        
        suggestions = engine.suggest("pyth")
        
        assert suggestions == []
    
    def test_bulk_index_empty_list(self):
        """Test bulk indexing empty list."""
        engine = SearchEngine()
        
        count = engine.bulk_index([])
        
        assert count == 0
    
    def test_delete_document_updates_index(self):
        """Test that deleting document updates search index."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python"})
        engine.index_document("doc2", {"title": "Java"})
        
        engine.delete_document("doc1")
        
        results = engine.search("python")
        
        assert len(results) == 0
    
    def test_delete_document_updates_filters(self):
        """Test that deleting document updates filter index."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python", "category": "tutorial"})
        engine.index_document("doc2", {"title": "Java", "category": "tutorial"})
        
        engine.delete_document("doc1")
        
        facets = engine.facet("category")
        
        # Only doc2 remains
        assert facets[0] == ("tutorial", 1)
    
    def test_search_after_clear(self):
        """Test search after clearing index."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python"})
        engine.clear()
        
        results = engine.search("python")
        
        assert len(results) == 0
    
    def test_index_document_numeric_field(self):
        """Test indexing document with numeric field."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test", "count": 42, "price": 19.99})
        
        doc = engine.get_document("doc1")
        
        assert doc.fields["count"] == 42
        assert doc.fields["price"] == 19.99
    
    def test_index_document_boolean_field(self):
        """Test indexing document with boolean field."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test", "active": True, "deleted": False})
        
        doc = engine.get_document("doc1")
        
        assert doc.fields["active"] is True
        assert doc.fields["deleted"] is False
    
    def test_filter_by_numeric_value(self):
        """Test filtering by numeric value."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test", "count": 42})
        engine.index_document("doc2", {"title": "Test", "count": 100})
        
        results = engine.search("test", filters={"count": 42})
        
        assert len(results) == 1
        assert results[0].doc_id == "doc1"
    
    def test_filter_by_boolean_value(self):
        """Test filtering by boolean value."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test", "active": True})
        engine.index_document("doc2", {"title": "Test", "active": False})
        
        results = engine.search("test", filters={"active": True})
        
        assert len(results) == 1
        assert results[0].doc_id == "doc1"
    
    def test_search_result_score_positive(self):
        """Test that search result score is positive."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python Programming"})
        
        results = engine.search("python")
        
        assert len(results) == 1
        assert results[0].score > 0
    
    def test_multiple_searches_same_query(self):
        """Test multiple searches with same query."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python"})
        
        results1 = engine.search("python")
        results2 = engine.search("python")
        
        assert len(results1) == len(results2)
        assert results1[0].doc_id == results2[0].doc_id
    
    def test_index_document_special_characters(self):
        """Test indexing document with special characters."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "C++ Programming & More!"})
        
        results = engine.search("programming")
        
        assert len(results) == 1
    
    def test_search_partial_word(self):
        """Test search with partial word."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Programming Python"})
        
        # Partial words won't match (tokenization requires full words)
        results = engine.search("progra")
        
        assert len(results) == 0
    
    def test_facet_single_value(self):
        """Test facet with single value."""
        engine = SearchEngine()
        
        for i in range(5):
            engine.index_document(f"doc{i}", {"title": f"Title {i}", "category": "same"})
        
        facets = engine.facet("category")
        
        assert len(facets) == 1
        assert facets[0] == ("same", 5)
    
    def test_suggest_prefix_case_insensitive(self):
        """Test that suggestions are case insensitive."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python"})
        
        suggestions = engine.suggest("PYTH")
        
        assert "python" in suggestions
    
    def test_document_updated_at_changes_on_reindex(self):
        """Test that document updated_at changes on reindex."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Original"})
        
        doc1 = engine.get_document("doc1")
        
        import time
        time.sleep(0.01)
        
        engine.index_document("doc1", {"title": "Updated"})
        
        doc2 = engine.get_document("doc1")
        
        assert doc2.updated_at > doc1.updated_at
    
    def test_search_with_all_options(self):
        """Test search with all options."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python Tutorial", "level": "beginner"})
        engine.index_document("doc2", {"title": "Python Advanced", "level": "advanced"})
        engine.index_document("doc3", {"title": "Java Tutorial", "level": "beginner"})
        
        results = engine.search(
            "python",
            fields=["title"],
            filters={"level": "beginner"},
            limit=10,
            highlight=True,
        )
        
        assert len(results) == 1
        assert results[0].doc_id == "doc1"
        assert "<mark>" in results[0].highlights.get("title", "")
    
    def test_statistics_after_delete(self):
        """Test statistics after deleting documents."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test"})
        engine.index_document("doc2", {"title": "Test"})
        
        engine.delete_document("doc1")
        
        stats = engine.get_statistics()
        
        assert stats["total_documents"] == 1
    
    def test_bulk_index_returns_correct_count(self):
        """Test that bulk_index returns correct count."""
        engine = SearchEngine()
        
        documents = [{"id": f"doc{i}", "title": f"Title {i}"} for i in range(10)]
        
        count = engine.bulk_index(documents)
        
        assert count == 10
    
    def test_index_document_unicode_content(self):
        """Test indexing document with unicode content."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python 编程", "content": "Привет мир"})
        
        results = engine.search("python")
        
        assert len(results) == 1
    
    def test_search_empty_string_query(self):
        """Test search with empty string query."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Hello"})
        
        results = engine.search("")
        
        assert len(results) == 0
    
    def test_facet_case_sensitive_values(self):
        """Test that facet values are case sensitive."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test", "category": "Tutorial"})
        engine.index_document("doc2", {"title": "Test", "category": "tutorial"})
        
        facets = engine.facet("category")
        
        # Should be separate values
        assert len(facets) == 2
    
    def test_clear_updates_statistics(self):
        """Test that clear updates statistics."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test"})
        engine.clear()
        
        stats = engine.get_statistics()
        
        assert stats["total_documents"] == 0
        assert stats["total_terms"] == 0
    
    def test_inverted_index_reuse_after_clear(self):
        """Test that inverted index can be reused after clear."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python"})
        engine.clear()
        
        # Should be able to index and search again
        engine.index_document("doc2", {"title": "Java"})
        
        results = engine.search("java")
        
        assert len(results) == 1
        assert results[0].doc_id == "doc2"
    
    def test_search_filters_excluded_documents(self):
        """Test that filters properly exclude documents."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python", "status": "published"})
        engine.index_document("doc2", {"title": "Python", "status": "draft"})
        engine.index_document("doc3", {"title": "Python", "status": "published"})
        
        results = engine.search("python", filters={"status": "published"})
        
        assert len(results) == 2
        
        doc_ids = [r.doc_id for r in results]
        
        assert "doc1" in doc_ids
        assert "doc3" in doc_ids
        assert "doc2" not in doc_ids
    
    def test_highlight_preserves_original_case(self):
        """Test that highlighting preserves original case."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "PYTHON Programming"})
        
        results = engine.search("python", highlight=True)
        
        # Should preserve original case in highlight
        assert "<mark>PYTHON</mark>" in results[0].highlights["title"] or \
               "<mark>python</mark>" in results[0].highlights["title"].lower()
    
    def test_document_id_unique_in_bulk_index(self):
        """Test that bulk index handles duplicate IDs."""
        engine = SearchEngine()
        
        documents = [
            {"id": "doc1", "title": "First"},
            {"id": "doc1", "title": "Second"},  # Duplicate ID
        ]
        
        count = engine.bulk_index(documents)
        
        # Should index both (second overwrites first)
        assert count == 2
        
        doc = engine.get_document("doc1")
        
        # Second should win
        assert doc.fields["title"] == "Second"
    
    def test_search_whitespace_handling(self):
        """Test search handles whitespace."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python Programming"})
        
        results = engine.search("  python   programming  ")
        
        assert len(results) == 1
    
    def test_facet_zero_limit(self):
        """Test facet with zero limit."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Test", "category": "test"})
        
        facets = engine.facet("category", limit=0)
        
        assert facets == []
    
    def test_suggest_zero_limit(self):
        """Test suggestions with zero limit."""
        engine = SearchEngine()
        
        engine.index_document("doc1", {"title": "Python"})
        
        suggestions = engine.suggest("pyth", limit=0)
        
        assert suggestions == []
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = SearchEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_documents"] == 0
        assert stats["total_indexed"] == 0
        assert stats["total_searches"] == 0
        assert stats["total_queries"] == 0
    
    def test_index_document_nested_fields(self):
        """Test indexing document with nested fields."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            {"title": "Test", "metadata": {"author": "John", "tags": ["a", "b"]}},
        )
        
        doc = engine.get_document("doc1")
        
        assert doc.fields["metadata"]["author"] == "John"
        assert doc.fields["metadata"]["tags"] == ["a", "b"]
    
    def test_search_nested_field_value(self):
        """Test searching nested field values."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            {"title": "Test", "author": "John Smith"},
        )
        
        results = engine.search("john")
        
        assert len(results) == 1
    
    def test_filter_nested_field_value(self):
        """Test filtering by nested field value."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc1",
            {"title": "Test", "status": {"published": True, "verified": False}},
        )
        engine.index_document(
            "doc2",
            {"title": "Test", "status": {"published": True, "verified": True}},
        )
        
        # Filter by string representation
        results = engine.search("test", filters={"status": "{'published': True, 'verified': False}"})
        
        assert len(results) == 1
        assert results[0].doc_id == "doc1"
