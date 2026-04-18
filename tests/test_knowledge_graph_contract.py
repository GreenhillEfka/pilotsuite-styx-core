"""Contract tests for the Knowledge Graph module.

Verifies:
- GraphStore initializes (SQLite fallback, Neo4j optional)
- GraphBuilder builds nodes/edges from HA data
- Node/Edge/GraphQuery/GraphResult models are correct dataclasses/enums
- kg_bp blueprint exists with url_prefix /api/v1/kg
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


class TestKnowledgeGraphModels:
    """Node/Edge/GraphQuery/GraphResult models are proper dataclasses."""

    def test_node_type_enum_has_entity(self):
        from copilot_core.knowledge_graph.models import NodeType
        assert hasattr(NodeType, "ENTITY")

    def test_node_type_enum_has_area(self):
        from copilot_core.knowledge_graph.models import NodeType
        assert hasattr(NodeType, "AREA")

    def test_node_type_enum_has_person(self):
        from copilot_core.knowledge_graph.models import NodeType
        assert hasattr(NodeType, "USER")

    def test_edge_type_enum_has_belongs_to(self):
        from copilot_core.knowledge_graph.models import EdgeType
        assert hasattr(EdgeType, "BELONGS_TO")

    def test_edge_type_enum_has_triggers(self):
        from copilot_core.knowledge_graph.models import EdgeType
        assert hasattr(EdgeType, "TRIGGERS")

    def test_node_dataclass(self):
        from copilot_core.knowledge_graph.models import Node
        node = Node(id="test-id", type=None, label="Test", properties={})
        assert node.id == "test-id"
        assert node.label == "Test"
        assert node.properties == {}

    def test_edge_dataclass(self):
        from copilot_core.knowledge_graph.models import Edge
        edge = Edge(source="n1", target="n2", type=None, weight=1.0, confidence=0.9, source_type="manual", evidence=[], created_at=0.0, updated_at=0.0)
        assert edge.source == "n1"
        assert edge.source == "n1"
        assert edge.target == "n2"

    def test_graph_query_dataclass(self):
        from copilot_core.knowledge_graph.models import GraphQuery
        q = GraphQuery(query_type="entities", max_results=50)
        assert q.max_results == 50

    def test_graph_result_dataclass(self):
        from copilot_core.knowledge_graph.models import GraphResult
        r = GraphResult(nodes=[], edges=[])
        assert r.nodes == []
        assert r.edges == []


class TestGraphStore:
    """GraphStore initializes and has expected CRUD methods."""

    def test_store_initializes(self):
        from copilot_core.knowledge_graph.graph_store import GraphStore
        store = GraphStore()
        assert store is not None

    def test_store_has_upsert_method(self):
        from copilot_core.knowledge_graph.graph_store import GraphStore
        store = GraphStore()
        assert hasattr(store, "upsert_node") or hasattr(store, "add_node")

    def test_store_has_query_method(self):
        from copilot_core.knowledge_graph.graph_store import GraphStore
        store = GraphStore()
        assert hasattr(store, "query") or hasattr(store, "execute_query")

    def test_store_has_get_node(self):
        from copilot_core.knowledge_graph.graph_store import GraphStore
        store = GraphStore()
        assert hasattr(store, "get_node")


class TestGraphBuilder:
    """GraphBuilder builds graph from HA data."""

    def test_builder_initializes(self):
        from copilot_core.knowledge_graph.builder import GraphBuilder
        builder = GraphBuilder()
        assert builder is not None

    def test_builder_has_upsert_entity(self):
        from copilot_core.knowledge_graph.builder import GraphBuilder
        builder = GraphBuilder()
        assert hasattr(builder, "upsert_entity")

    def test_builder_has_build_from_ha_states(self):
        from copilot_core.knowledge_graph.builder import GraphBuilder
        builder = GraphBuilder()
        assert hasattr(builder, "build_from_ha_states")

    def test_builder_has_upsert_zone(self):
        from copilot_core.knowledge_graph.builder import GraphBuilder
        builder = GraphBuilder()
        assert hasattr(builder, "upsert_zone")


class TestKnowledgeGraphAPI:
    """Knowledge Graph API blueprint is importable and registered."""

    def test_kg_api_bp_importable(self):
        from copilot_core.knowledge_graph.api import bp as kg_bp
        assert kg_bp is not None
        assert kg_bp.url_prefix == "/kg"

    def test_kg_api_has_query_endpoint(self):
        from flask import Flask
        from copilot_core.knowledge_graph.api import bp as kg_bp
        app = Flask(__name__)
        app.register_blueprint(kg_bp)
        rules = {str(r): r.methods for r in app.url_map.iter_rules()}
        assert "/kg/nodes" in rules or "/kg/query" in rules

    def test_kg_api_has_stats_endpoint(self):
        from flask import Flask
        from copilot_core.knowledge_graph.api import bp as kg_bp
        app = Flask(__name__)
        app.register_blueprint(kg_bp)
        rules = {str(r): r.methods for r in app.url_map.iter_rules()}
        assert "/kg/stats" in rules