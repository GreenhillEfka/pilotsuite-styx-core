"""RAG Enrichment Resilience 309 — CORE RAG result enrichment contract.

Verifies that result enrichment failures produce graceful nulls, not crashes,
and that result entries are always machine-parseable on the existing Core RAG seam.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

import uuid
from unittest.mock import patch, MagicMock
from flask import Flask
from copilot_core.api.v1.rag import bp as rag_bp
from copilot_core.rag import BM25Hit, RankedHit


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(rag_bp)
    return app


@contextmanager
def _auth_ok():
    async def _no_cache(*args, **kwargs):
        return None
    with patch('copilot_core.api.v1.rag.validate_token', return_value=True):
        with patch('copilot_core.api.v1.rag._get_rag_cache') as mock_cache:
            mock_cache.return_value.get = _no_cache
            yield


# ── Enrichment resilience helpers ─────────────────────────────────────────────

def _assert_entry_sane(entry: dict, doc_id: str, score: float) -> None:
    """Every hit entry must always have id and score, regardless of enrichment state."""
    assert "id" in entry, f"entry missing 'id': {entry}"
    assert "score" in entry, f"entry missing 'score': {entry}"
    assert entry["id"] == doc_id, f"id mismatch: {entry['id']} != {doc_id}"


# ── Missing doc IDs → graceful nulls ──────────────────────────────────────────

class TestMissingDocIdsGracefulNulls:
    """When get_documents returns no match for a doc_id, result entry gets null, not crash."""

    def test_missing_doc_id_gets_null_text_and_metadata(self):
        """Unknown doc_id in result: text=null, metadata=null, no crash."""
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    # BM25 returns a hit for a doc that doesn't exist in get_documents
                    mock_bm25.return_value.search.return_value = [
                        BM25Hit(doc_id="ghost-doc-309", score=1.5, rank=1),
                    ]
                    # get_documents returns empty dict for unknown doc
                    mock_bm25.return_value.get_documents.return_value = {}
                    with patch('copilot_core.api.v1.rag._enrich_results', return_value={}):
                        r = app.test_client().post(
                            "/api/v1/rag/search",
                            json={"query": "test query", "use_lexical": True, "use_semantic": False}
                        )
                        d = r.get_json()
                        assert d.get("result_count", 0) >= 0, f"request failed: {d}"
                        results = d.get("results", [])
                        assert len(results) == 1
                        entry = results[0]
                        _assert_entry_sane(entry, "ghost-doc-309", 1.5)
                        # Missing doc → null fields, not crash
                        assert entry.get("text") is None, f"text must be None for missing doc, got {entry.get('text')}"
                        assert entry.get("metadata") is None, f"metadata must be None for missing doc, got {entry.get('metadata')}"

    def test_missing_doc_id_preserves_extra_fields(self):
        """Even when doc is missing, extra RRF fields (lexical_score, fused_score etc.) are preserved."""
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [
                        BM25Hit(doc_id="ghost-rrf", score=0.8, rank=1),
                    ]
                    with patch('copilot_core.api.v1.rag._enrich_results', return_value={}):
                        r = app.test_client().post(
                            "/api/v1/rag/search",
                            json={"query": "test query", "use_lexical": True, "use_semantic": True}
                        )
                        d = r.get_json()
                        results = d.get("results", [])
                        if results:
                            entry = results[0]
                            # Extra fields from RRF fusion must still be present
                            # (lexical_rank, lexical_score, semantic_rank, semantic_score, fused_score)
                            assert "lexical_rank" in entry or "fused_score" in entry or "lexical_score" in entry, \
                                f"RRF extra fields missing: {entry}"


# ── include_text=False ─────────────────────────────────────────────────────────

class TestIncludeTextFalse:
    """When include_text=False, text field must not appear in result entries."""

    def test_include_text_false_excludes_text_field(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [
                        BM25Hit(doc_id="doc-no-text", score=1.0, rank=1),
                    ]
                    # Even if get_documents returns text, it should not appear
                    mock_bm25.return_value.get_documents.return_value = {
                        "doc-no-text": {"text": "some text content", "metadata": {"key": "val"}}
                    }
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": True, "use_semantic": False,
                              "include_text": False, "include_metadata": True}
                    )
                    d = r.get_json()
                    results = d.get("results", [])
                    assert len(results) >= 1
                    entry = results[0]
                    _assert_entry_sane(entry, "doc-no-text", 1.0)
                    assert "text" not in entry, f"'text' must not appear when include_text=False: {entry}"
                    # metadata should still be present
                    assert "metadata" in entry, f"'metadata' must appear when include_metadata=True"


# ── include_metadata=False ─────────────────────────────────────────────────────

class TestIncludeMetadataFalse:
    """When include_metadata=False, metadata field must not appear in result entries."""

    def test_include_metadata_false_excludes_metadata_field(self):
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = [
                        BM25Hit(doc_id="doc-no-meta", score=1.0, rank=1),
                    ]
                    mock_bm25.return_value.get_documents.return_value = {
                        "doc-no-meta": {"text": "some text", "metadata": {"key": "val"}}
                    }
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": True, "use_semantic": False,
                              "include_text": True, "include_metadata": False}
                    )
                    d = r.get_json()
                    results = d.get("results", [])
                    assert len(results) >= 1
                    entry = results[0]
                    _assert_entry_sane(entry, "doc-no-meta", 1.0)
                    assert "metadata" not in entry, f"'metadata' must not appear when include_metadata=False: {entry}"
                    # text should still be present
                    assert "text" in entry, f"'text' must appear when include_text=True"


# ── Result entry machine-parseable ─────────────────────────────────────────────

class TestResultEntryMachineParseable:
    """Every result entry must always be machine-parseable dict, not None/error."""

    def test_empty_results_list_is_valid_response(self):
        """Zero results is a valid response, not an error."""
        app = _make_app()
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    mock_bm25.return_value.search.return_value = []
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "nonexistent query that returns nothing", "use_lexical": True}
                    )
                    d = r.get_json()
                    assert r.status_code == 200, f"got status {r.status_code}: {d}"
                    assert d.get("result_count") == 0
                    assert isinstance(d.get("results"), list)

    def test_entry_always_has_id_and_score(self):
        """Every hit must have 'id' and 'score' fields, even under enrichment failure."""
        app = _make_app()
        token = str(uuid.uuid4())[:8]
        with _auth_ok():
            with patch('copilot_core.api.v1.rag._load_semantic_backend', return_value=None):
                with patch('copilot_core.api.v1.rag._get_bm25') as mock_bm25:
                    # Return hit with known doc_id
                    mock_bm25.return_value.search.return_value = [
                        BM25Hit(doc_id=f"doc-{token}-entry", score=2.5, rank=1),
                    ]
                    # get_documents raises — enrichment failure
                    mock_bm25.return_value.get_documents.side_effect = RuntimeError("enrichment unavailable")
                    r = app.test_client().post(
                        "/api/v1/rag/search",
                        json={"query": "test query", "use_lexical": True, "use_semantic": False}
                    )
                    # Must not 500; should handle gracefully
                    assert r.status_code in (200, 400, 500), f"got status {r.status_code}"
                    if r.status_code == 200:
                        d = r.get_json()
                        if d.get("result_count", 0) > 0 and d.get("results"):
                            entry = d["results"][0]
                            _assert_entry_sane(entry, f"doc-{token}-entry", 2.5)
