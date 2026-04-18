"""Contract tests for Brain Graph Live Bridge delta fields.

Verifies build_graph_update_payload enriches the WebSocket payload
with canvas-actionable delta fields: change_type, node_id, edge_id, pruned_stats.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


class TestBuildGraphUpdatePayload:
    """build_graph_update_payload returns canvas-actionable delta fields."""

    def test_node_updated_sets_delta_node_id(self):
        from copilot_core.websocket_handler import build_graph_update_payload

        event = {
            "event": "node_updated",
            "data": {"id": "sensor.living_room", "kind": "ENTITY", "label": "Living Room", "score": 0.95},
            "timestamp_ms": 1713420800000,
        }
        payload = build_graph_update_payload({"nodes": 42, "edges": 15}, event)

        assert payload["source_event"] == "node_updated"
        assert payload["delta"]["change_type"] == "node_updated"
        assert payload["delta"]["node_id"] == "sensor.living_room"
        assert payload["delta"]["edge_id"] is None
        assert payload["delta"]["pruned_stats"] is None
        assert payload["event_data"]["id"] == "sensor.living_room"

    def test_edge_updated_sets_delta_edge_id(self):
        from copilot_core.websocket_handler import build_graph_update_payload

        event = {
            "event": "edge_updated",
            "data": {"id": "e123", "from": "room.1", "to": "entity.42", "type": "CONTAINS", "weight": 0.8},
            "timestamp_ms": 1713420801000,
        }
        payload = build_graph_update_payload({"nodes": 42, "edges": 16}, event)

        assert payload["source_event"] == "edge_updated"
        assert payload["delta"]["change_type"] == "edge_updated"
        assert payload["delta"]["edge_id"] == "e123"
        assert payload["delta"]["node_id"] is None
        assert payload["delta"]["pruned_stats"] is None

    def test_graph_pruned_sets_delta_pruned_stats(self):
        from copilot_core.websocket_handler import build_graph_update_payload

        event = {
            "event": "graph_pruned",
            "data": {"nodes_removed": 3, "edges_removed": 7, "pruned_at": 1713420800},
            "timestamp_ms": 1713420802000,
        }
        payload = build_graph_update_payload({"nodes": 39, "edges": 9}, event)

        assert payload["source_event"] == "graph_pruned"
        assert payload["delta"]["change_type"] == "pruned"
        assert payload["delta"]["pruned_stats"]["nodes_removed"] == 3
        assert payload["delta"]["pruned_stats"]["edges_removed"] == 7
        assert payload["delta"]["node_id"] is None
        assert payload["delta"]["edge_id"] is None

    def test_no_event_returns_delta_none(self):
        from copilot_core.websocket_handler import build_graph_update_payload

        payload = build_graph_update_payload({"nodes": 42, "edges": 15}, None)

        assert payload["source_event"] is None
        assert payload["delta"]["change_type"] is None
        assert payload["delta"]["node_id"] is None
        assert payload["delta"]["edge_id"] is None
        assert payload["delta"]["pruned_stats"] is None

    def test_delta_embedded_under_delta_key(self):
        from copilot_core.websocket_handler import build_graph_update_payload

        payload = build_graph_update_payload(
            {"nodes": 10, "edges": 5},
            {"event": "node_updated", "data": {"id": "test.node"}, "timestamp_ms": 1}
        )

        assert "delta" in payload
        assert isinstance(payload["delta"], dict)
        assert "change_type" in payload["delta"]
        assert "node_id" in payload["delta"]
        assert "edge_id" in payload["delta"]
        assert "pruned_stats" in payload["delta"]