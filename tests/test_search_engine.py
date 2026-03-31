"""Tests for Search Engine — Slice 32."""
import pytest
from copilot_core.search.engine import (
    SearchEngine,
    SearchMatchType,
    SearchIndex,
    SearchResult,
    SearchQuery,
    create_search_engine,
)


class TestSearchEngine:
    """Test search engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_search_engine()
        assert engine is not None
    
    def test_index_document(self):
        """Test indexing a document."""
        engine = SearchEngine()
        
        index_id = engine.index_document(
            document_id="doc_001",
            document_type="article",
            content="This is a test article about home automation.",
            metadata={"author": "test", "category": "tech"},
        )
        
        assert index_id is not None
        assert index_id.startswith("idx_")
        assert "doc_001" in [i.document_id for i in engine._indices.values()]
    
    def test_index_document_updates_existing(self):
        """Test that re-indexing updates existing document."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Original content")
        engine.index_document("doc_001", "article", "Updated content")
        
        indices = engine.get_all_indices()
        
        assert len(indices) == 1
        assert "Updated" in indices[0]["content"]
    
    def test_remove_document(self):
        """Test removing a document."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Test content")
        
        result = engine.remove_document("doc_001")
        
        assert result is True
        assert len(engine._indices) == 0
    
    def test_remove_nonexistent_document(self):
        """Test removing nonexistent document."""
        engine = SearchEngine()
        
        result = engine.remove_document("nonexistent")
        
        assert result is False
    
    def test_search_exact_match(self):
        """Test exact match search."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation is great")
        engine.index_document("doc_002", "article", "Smart home devices")
        engine.index_document("doc_003", "blog", "Automation tips")
        
        results = engine.search("automation", match_type="exact")
        
        assert len(results) >= 1
        assert results[0].document_id == "doc_001"
    
    def test_search_fuzzy_match(self):
        """Test fuzzy match search."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation")
        engine.index_document("doc_002", "article", "Home automatoin")  # Typo
        
        results = engine.search("automation", match_type="fuzzy")
        
        assert len(results) >= 1
    
    def test_search_prefix_match(self):
        """Test prefix match search."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation system")
        engine.index_document("doc_002", "article", "Automated lighting")
        
        results = engine.search("auto", match_type="prefix")
        
        assert len(results) >= 1
    
    def test_search_contains_match(self):
        """Test contains match search."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation")
        
        results = engine.search("tomat", match_type="contains")
        
        assert len(results) >= 1
    
    def test_search_with_document_type_filter(self):
        """Test search with document type filter."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation")
        engine.index_document("doc_002", "blog", "Automation tips")
        
        results = engine.search("automation", document_types=["article"])
        
        assert len(results) == 1
        assert results[0].document_type == "article"
    
    def test_search_with_metadata_filter(self):
        """Test search with metadata filter."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation", 
                             metadata={"author": "john"})
        engine.index_document("doc_002", "article", "Smart home",
                             metadata={"author": "jane"})
        
        results = engine.search("home", filters={"author": "john"})
        
        assert len(results) == 1
        assert results[0].document_id == "doc_001"
    
    def test_search_score_ordering(self):
        """Test that results are ordered by score."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation home automation home")
        engine.index_document("doc_002", "article", "Home")
        
        results = engine.search("home automation")
        
        assert results[0].score >= results[1].score
    
    def test_search_limit(self):
        """Test search result limit."""
        engine = SearchEngine()
        
        for i in range(10):
            engine.index_document(f"doc_{i:03d}", "article", f"Test content {i}")
        
        results = engine.search("test", limit=5)
        
        assert len(results) <= 5
    
    def test_search_min_score(self):
        """Test search minimum score threshold."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation")
        engine.index_document("doc_002", "article", "Something unrelated")
        
        results = engine.search("automation", min_score=0.5)
        
        assert len(results) == 1
        assert results[0].document_id == "doc_001"
    
    def test_get_index(self):
        """Test getting index for a document."""
        engine = SearchEngine()
        
        engine.index_document(
            "doc_001", 
            "article", 
            "Test content",
            metadata={"author": "test"},
        )
        
        index = engine.get_index("doc_001")
        
        assert index is not None
        assert index["document_id"] == "doc_001"
        assert index["document_type"] == "article"
    
    def test_get_unknown_index(self):
        """Test getting unknown index."""
        engine = SearchEngine()
        
        index = engine.get_index("nonexistent")
        
        assert index is None
    
    def test_get_all_indices(self):
        """Test getting all indices."""
        engine = SearchEngine()
        
        for i in range(5):
            engine.index_document(f"doc_{i}", "article", f"Content {i}")
        
        indices = engine.get_all_indices()
        
        assert len(indices) == 5
    
    def test_get_all_indices_filtered_by_type(self):
        """Test getting indices filtered by type."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Content")
        engine.index_document("doc_002", "blog", "Content")
        engine.index_document("doc_003", "article", "Content")
        
        articles = engine.get_all_indices(document_type="article")
        
        assert len(articles) == 2
        assert all(i["document_type"] == "article" for i in articles)
    
    def test_get_search_facets(self):
        """Test getting search facets."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Content", metadata={"author": "john"})
        engine.index_document("doc_002", "blog", "Content", metadata={"author": "jane"})
        engine.index_document("doc_003", "article", "Content", metadata={"author": "john"})
        
        facets = engine.get_search_facets()
        
        assert "document_types" in facets
        assert facets["document_types"]["article"] == 2
        assert facets["document_types"]["blog"] == 1
    
    def test_get_search_statistics(self):
        """Test getting search statistics."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation")
        engine.search("home")
        engine.search("automation")
        
        stats = engine.get_search_statistics()
        
        assert stats["documents_indexed"] == 1
        assert stats["searches"] == 2
        assert stats["total_queries"] == 2
    
    def test_clear_indices(self):
        """Test clearing all indices."""
        engine = SearchEngine()
        
        for i in range(5):
            engine.index_document(f"doc_{i}", "article", f"Content {i}")
        
        count = engine.clear_indices()
        
        assert count == 5
        assert len(engine._indices) == 0
    
    def test_rebuild_index(self):
        """Test rebuilding index."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Original content")
        
        result = engine.rebuild_index("doc_001", "New content")
        
        assert result is True
        
        index = engine.get_index("doc_001")
        assert "New" in index["content"]
    
    def test_rebuild_nonexistent_index(self):
        """Test rebuilding nonexistent index."""
        engine = SearchEngine()
        
        result = engine.rebuild_index("nonexistent", "Content")
        
        assert result is False
    
    def test_fuzzy_match_exact(self):
        """Test fuzzy match with exact strings."""
        engine = SearchEngine()
        
        similarity = engine._fuzzy_match("automation", "automation")
        
        assert similarity == 1.0
    
    def test_fuzzy_match_similar(self):
        """Test fuzzy match with similar strings."""
        engine = SearchEngine()
        
        similarity = engine._fuzzy_match("automation", "automaton")
        
        assert similarity > 0.8
    
    def test_fuzzy_match_different(self):
        """Test fuzzy match with different strings."""
        engine = SearchEngine()
        
        similarity = engine._fuzzy_match("automation", "completely")
        
        assert similarity < 0.5
    
    def test_fuzzy_match_empty(self):
        """Test fuzzy match with empty string."""
        engine = SearchEngine()
        
        similarity = engine._fuzzy_match("", "automation")
        
        assert similarity == 0.0
    
    def test_tokenize_lowercase(self):
        """Test tokenization converts to lowercase."""
        engine = SearchEngine()
        
        tokens = engine._tokenize("HOME Automation")
        
        assert "home" in tokens
        assert "automation" in tokens
    
    def test_tokenize_removes_special_chars(self):
        """Test tokenization removes special characters."""
        engine = SearchEngine()
        
        tokens = engine._tokenize("Home-automation! System?")
        
        assert "home" in tokens
        assert "automation" in tokens
        assert "system" in tokens
    
    def test_tokenize_removes_short_tokens(self):
        """Test tokenization removes short tokens."""
        engine = SearchEngine()
        
        tokens = engine._tokenize("A an the home")
        
        assert "a" not in tokens
        assert "an" not in tokens
        assert "the" in tokens  # 3 chars
        assert "home" in tokens
    
    def test_generate_highlights(self):
        """Test highlight generation."""
        engine = SearchEngine()
        
        content = "Home automation is a great way to control your home. " \
                  "With home automation, you can automate everything."
        
        highlights = engine._generate_highlights(content, {"home", "automation"})
        
        assert len(highlights) >= 1
        assert any("home" in h.lower() for h in highlights)
    
    def test_matches_filters_all_match(self):
        """Test filter matching when all match."""
        engine = SearchEngine()
        
        metadata = {"author": "john", "category": "tech"}
        filters = {"author": "john", "category": "tech"}
        
        result = engine._matches_filters(metadata, filters)
        
        assert result is True
    
    def test_matches_filters_partial_match(self):
        """Test filter matching when partial match."""
        engine = SearchEngine()
        
        metadata = {"author": "john", "category": "tech"}
        filters = {"author": "jane"}
        
        result = engine._matches_filters(metadata, filters)
        
        assert result is False
    
    def test_matches_filters_missing_key(self):
        """Test filter matching when key missing."""
        engine = SearchEngine()
        
        metadata = {"author": "john"}
        filters = {"category": "tech"}
        
        result = engine._matches_filters(metadata, filters)
        
        assert result is False
    
    def test_search_result_to_dict(self):
        """Test search result serialization."""
        result = SearchResult(
            document_id="doc_001",
            document_type="article",
            score=0.85,
            matched_tokens=["home", "automation"],
            highlights=["...home automation..."],
            metadata={"author": "test"},
        )
        
        d = result.to_dict()
        
        assert d["document_id"] == "doc_001"
        assert d["score"] == 0.85
        assert len(d["matched_tokens"]) == 2
    
    def test_search_query_to_dict(self):
        """Test search query serialization."""
        query = SearchQuery(
            query_text="home automation",
            match_type=SearchMatchType.FUZZY,
            document_types=["article"],
            filters={"author": "test"},
            limit=25,
        )
        
        d = query.to_dict()
        
        assert d["query_text"] == "home automation"
        assert d["match_type"] == "fuzzy"
        assert d["limit"] == 25
    
    def test_search_index_to_dict(self):
        """Test search index serialization."""
        index = SearchIndex(
            index_id="idx_001",
            document_id="doc_001",
            document_type="article",
            content="Test content " * 100,  # Long content
            metadata={"author": "test"},
            tokens={"test", "content"},
        )
        
        d = index.to_dict()
        
        assert d["index_id"] == "idx_001"
        assert len(d["content"]) <= 203  # Truncated with "..."
        assert d["token_count"] == 2
    
    def test_search_match_type_enum_values(self):
        """Test search match type enum values."""
        assert SearchMatchType.EXACT.value == "exact"
        assert SearchMatchType.FUZZY.value == "fuzzy"
        assert SearchMatchType.PREFIX.value == "prefix"
        assert SearchMatchType.CONTAINS.value == "contains"
        assert SearchMatchType.REGEX.value == "regex"
    
    def test_search_boosts_exact_matches(self):
        """Test that exact matches get score boost."""
        engine = SearchEngine()
        
        # Document with exact match
        engine.index_document("doc_001", "article", "home automation")
        # Document with fuzzy match only
        engine.index_document("doc_002", "article", "home automatoin")
        
        results = engine.search("automation", match_type="fuzzy")
        
        # Exact match should score higher
        exact_result = next(r for r in results if r.document_id == "doc_001")
        fuzzy_result = next(r for r in results if r.document_id == "doc_002")
        
        assert exact_result.score > fuzzy_result.score
    
    def test_search_empty_query(self):
        """Test search with empty query."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Home automation")
        
        results = engine.search("")
        
        assert len(results) == 0
    
    def test_multiple_searches_accumulate_stats(self):
        """Test that multiple searches accumulate statistics."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Test")
        
        for i in range(5):
            engine.search("test")
        
        stats = engine.get_search_statistics()
        
        assert stats["searches"] == 5
        assert stats["total_queries"] == 5
    
    def test_index_with_empty_metadata(self):
        """Test indexing with empty metadata."""
        engine = SearchEngine()
        
        index_id = engine.index_document(
            "doc_001",
            "article",
            "Test content",
            metadata={},
        )
        
        index = engine.get_index("doc_001")
        
        assert index is not None
        assert index["metadata"] == {}
    
    def test_index_without_metadata(self):
        """Test indexing without metadata parameter."""
        engine = SearchEngine()
        
        index_id = engine.index_document(
            "doc_001",
            "article",
            "Test content",
        )
        
        index = engine.get_index("doc_001")
        
        assert index is not None
        assert index["metadata"] == {}
    
    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "HOME AUTOMATION")
        
        results1 = engine.search("home")
        results2 = engine.search("HOME")
        results3 = engine.search("HoMe")
        
        assert len(results1) == len(results2) == len(results3)
        assert len(results1) >= 1
    
    def test_facets_empty_index(self):
        """Test facets with empty index."""
        engine = SearchEngine()
        
        facets = engine.get_search_facets()
        
        assert facets["document_types"] == {}
        assert facets["metadata_fields"] == {}
    
    def test_facets_filtered_by_type(self):
        """Test facets filtered by document type."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "Content", metadata={"author": "john"})
        engine.index_document("doc_002", "blog", "Content", metadata={"author": "jane"})
        
        facets = engine.get_search_facets(document_type="article")
        
        assert facets["document_types"]["article"] == 1
        assert "blog" not in facets["document_types"]
    
    def test_statistics_unique_tokens(self):
        """Test statistics unique token count."""
        engine = SearchEngine()
        
        engine.index_document("doc_001", "article", "home automation")
        engine.index_document("doc_002", "article", "smart home")
        
        stats = engine.get_search_statistics()
        
        # Should have: home, automation, smart (home is duplicated)
        assert stats["unique_tokens"] >= 2
    
    def test_statistics_empty_index(self):
        """Test statistics with empty index."""
        engine = SearchEngine()
        
        stats = engine.get_search_statistics()
        
        assert stats["documents_indexed"] == 0
        assert stats["unique_tokens"] == 0
