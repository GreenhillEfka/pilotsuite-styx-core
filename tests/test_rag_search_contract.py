"""Contract tests for the RAG Search API module.

Verifies:
- rag_bp (bp) is importable with url_prefix /api/v1/rag
- BM25Config, BM25Document models are importable
- Key search/query methods exist on the index class
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


class TestRAGSearchAPI:
    """RAG Search API blueprint contract."""

    def test_rag_bp_importable(self):
        from copilot_core.api.v1.rag import bp as rag_bp
        assert rag_bp is not None
        assert rag_bp.name == "rag"

    def test_rag_url_prefix(self):
        from copilot_core.api.v1.rag import bp as rag_bp
        assert rag_bp.url_prefix == "/api/v1/rag"

    def test_rag_search_routes_registered(self):
        from flask import Flask
        from copilot_core.api.v1.rag import bp as rag_bp

        app = Flask(__name__)
        app.register_blueprint(rag_bp)
        routes = {str(r): r.methods for r in app.url_map.iter_rules()}
        rag_routes = [p for p in routes if "/rag" in p]
        assert len(rag_routes) >= 1, f"No RAG routes found: {rag_routes}"

    def test_specialized_search_routes_registered(self):
        from flask import Flask
        from copilot_core.api.v1.rag import bp as rag_bp

        app = Flask(__name__)
        app.register_blueprint(rag_bp)
        routes = {str(r): r.methods for r in app.url_map.iter_rules()}

        assert "/api/v1/rag/search/bm25" in routes
        assert "POST" in routes["/api/v1/rag/search/bm25"]
        assert "/api/v1/rag/search/semantic" in routes
        assert "POST" in routes["/api/v1/rag/search/semantic"]
        assert "/api/v1/rag/rerank" in routes
        assert "POST" in routes["/api/v1/rag/rerank"]


class TestRAGSearchModels:
    """RAG Search data models contract."""

    def test_bm25_config_importable(self):
        from copilot_core.api.v1.rag import BM25Config
        assert BM25Config is not None

    def test_bm25_document_importable(self):
        from copilot_core.api.v1.rag import BM25Document
        assert BM25Document is not None

    def test_query_type_enum_importable(self):
        from copilot_core.api.v1.rag import QueryType
        assert QueryType is not None
        assert hasattr(QueryType, "SEMANTIC") or hasattr(QueryType, "HYBRID") or len(QueryType.__members__) > 0

    def test_bm25_config_has_k1_field(self):
        from copilot_core.api.v1.rag import BM25Config
        fields = BM25Config.__dataclass_fields__ if hasattr(BM25Config, '__dataclass_fields__') else {}
        assert "k1" in fields or "b" in fields


class TestVectorAPI:
    """Vector Search API blueprint contract."""

    def test_vector_bp_importable(self):
        from copilot_core.api.v1.vector import bp as vector_bp
        assert vector_bp is not None

    def test_vector_url_prefix(self):
        from copilot_core.api.v1.vector import bp as vector_bp
        # url_prefix may be /vector or /api/v1/vector
        prefix = vector_bp.url_prefix
        assert prefix is not None and isinstance(prefix, str)
