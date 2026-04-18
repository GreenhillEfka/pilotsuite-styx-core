"""Contract tests for the Brain Graph module.

Verifies:
- GraphNode/GraphEdge dataclasses have expected fields
- GraphStore has get_nodes/get_edges/get_node/get_neighborhood methods
- BrainGraphService has expected methods (get_stats, get_graph_state, batch ops)
- brain_graph_bp is importable with /api/v1/graph prefix
- All routes are registered (/state, /stats, /nodes, /snapshot.svg, etc.)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


class TestBrainGraphModels:
    """GraphNode/GraphEdge dataclasses have expected fields."""

    def test_graph_node_has_id(self):
        from copilot_core.brain_graph import GraphNode
        assert "id" in GraphNode.__dataclass_fields__

    def test_graph_node_has_kind(self):
        from copilot_core.brain_graph import GraphNode
        assert "kind" in GraphNode.__dataclass_fields__

    def test_graph_node_has_label(self):
        from copilot_core.brain_graph import GraphNode
        assert "label" in GraphNode.__dataclass_fields__

    def test_graph_node_has_score(self):
        from copilot_core.brain_graph import GraphNode
        assert "score" in GraphNode.__dataclass_fields__

    def test_graph_edge_has_from_node(self):
        from copilot_core.brain_graph import GraphEdge
        assert "from_node" in GraphEdge.__dataclass_fields__

    def test_graph_edge_has_to_node(self):
        from copilot_core.brain_graph import GraphEdge
        assert "to_node" in GraphEdge.__dataclass_fields__

    def test_graph_edge_has_edge_type(self):
        from copilot_core.brain_graph import GraphEdge
        assert "edge_type" in GraphEdge.__dataclass_fields__

    def test_graph_edge_has_weight(self):
        from copilot_core.brain_graph import GraphEdge
        assert "weight" in GraphEdge.__dataclass_fields__


class TestGraphStore:
    """GraphStore has the expected query methods."""

    def test_store_has_get_nodes(self):
        from copilot_core.brain_graph import GraphStore
        store = GraphStore()
        assert hasattr(store, "get_nodes")

    def test_store_has_get_edges(self):
        from copilot_core.brain_graph import GraphStore
        store = GraphStore()
        assert hasattr(store, "get_edges")

    def test_store_has_get_node(self):
        from copilot_core.brain_graph import GraphStore
        store = GraphStore()
        assert hasattr(store, "get_node")

    def test_store_has_get_neighborhood(self):
        from copilot_core.brain_graph import GraphStore
        store = GraphStore()
        assert hasattr(store, "get_neighborhood")


class TestBrainGraphService:
    """BrainGraphService has expected operations methods."""

    def test_service_has_get_stats(self):
        from copilot_core.brain_graph import BrainGraphService
        svc = BrainGraphService()
        assert hasattr(svc, "get_stats")

    def test_service_has_get_graph_state(self):
        from copilot_core.brain_graph import BrainGraphService
        svc = BrainGraphService()
        assert hasattr(svc, "get_graph_state")

    def test_service_has_batch_methods(self):
        from copilot_core.brain_graph import BrainGraphService
        svc = BrainGraphService()
        assert hasattr(svc, "begin_batch")
        assert hasattr(svc, "commit_batch")


class TestBrainGraphAPI:
    """Brain Graph API blueprint is importable and routes are registered."""

    def test_bp_importable(self):
        from copilot_core.brain_graph.api import brain_graph_bp
        assert brain_graph_bp is not None

    def test_bp_url_prefix(self):
        from copilot_core.brain_graph.api import brain_graph_bp
        assert brain_graph_bp.url_prefix == "/api/v1/graph"

    def test_state_endpoint_defined(self):
        """Verify get_graph_state function exists in brain_graph.api module."""
        from copilot_core.brain_graph import api as bg_api
        assert hasattr(bg_api, "get_graph_state")

    def test_stats_endpoint_defined(self):
        """Verify get_graph_stats function exists in brain_graph.api module."""
        from copilot_core.brain_graph import api as bg_api
        assert hasattr(bg_api, "get_graph_stats")

    def test_nodes_endpoint_defined(self):
        """Verify get_nodes_paginated function exists in brain_graph.api module."""
        from copilot_core.brain_graph import api as bg_api
        assert hasattr(bg_api, "get_nodes_paginated")

    def test_snapshot_svg_endpoint_defined(self):
        """Verify get_graph_snapshot function exists (serves /snapshot.svg)."""
        from copilot_core.brain_graph import api as bg_api
        assert hasattr(bg_api, "get_graph_snapshot")

    def test_patterns_endpoint_defined(self):
        """Verify get_patterns function exists in brain_graph.api module."""
        from copilot_core.brain_graph import api as bg_api
        assert hasattr(bg_api, "get_patterns")

    def test_prune_endpoint_defined(self):
        """Verify prune_graph function exists in brain_graph.api module."""
        from copilot_core.brain_graph import api as bg_api
        assert hasattr(bg_api, "prune_graph")