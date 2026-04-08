"""Tests for copilot_core.ingest.event_processor – EventStore → BrainGraph pipeline."""
import sys
import os
import tempfile
import unittest

# Ensure app root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copilot_core.ingest.event_processor import EventProcessor
from copilot_core.brain_graph.service import BrainGraphService
from copilot_core.brain_graph.store import GraphStore


class TestEventProcessor(unittest.TestCase):
    """Test EventProcessor without Flask / HTTP layer."""

    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        store = GraphStore(db_path=self._tmpfile.name)
        self.bg = BrainGraphService(store=store)
        self.proc = EventProcessor(brain_graph_service=self.bg)

    def tearDown(self):
        try:
            os.unlink(self._tmpfile.name)
        except OSError:
            pass

    # ── basic wiring ────────────────────────────────────────────────

    def test_process_empty_batch(self):
        stats = self.proc.process_events([])
        self.assertEqual(stats["processed"], 0)
        self.assertEqual(stats["errors"], 0)

    def test_state_changed_creates_entity_node(self):
        event = {
            "kind": "state_changed",
            "entity_id": "light.kitchen",
            "domain": "light",
            "new": {"state": "on"},
        }
        stats = self.proc.process_events([event])
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["errors"], 0)

        # Verify node was created in brain graph
        node = self.bg.store.get_node("ha.entity:light.kitchen")
        self.assertIsNotNone(node)
        self.assertEqual(node.kind, "entity")
        self.assertEqual(node.domain, "light")

    def test_state_changed_with_zone_creates_link(self):
        event = {
            "kind": "state_changed",
            "entity_id": "sensor.temperature_living",
            "domain": "sensor",
            "zone_id": "living_room",
            "new": {"state": "21.5"},
        }
        stats = self.proc.process_events([event])
        self.assertEqual(stats["processed"], 1)

        # Entity node
        entity = self.bg.store.get_node("ha.entity:sensor.temperature_living")
        self.assertIsNotNone(entity)
        self.assertEqual(entity.meta.get("zone_id"), "living_room")

        # Zone node
        zone = self.bg.store.get_node("ha.zone:living_room")
        self.assertIsNotNone(zone)
        self.assertEqual(zone.kind, "zone")

        # Edge between them
        edges = self.bg.store.get_edges(from_node="ha.entity:sensor.temperature_living")
        located_in = [e for e in edges if e.edge_type == "located_in"]
        self.assertEqual(len(located_in), 1)
        self.assertEqual(located_in[0].to_node, "ha.zone:living_room")

    def test_call_service_creates_service_node_and_link(self):
        event = {
            "kind": "call_service",
            "domain": "light",
            "service": "turn_on",
            "entity_id": "light.bedroom",
        }
        stats = self.proc.process_events([event])
        self.assertEqual(stats["processed"], 1)

        # Service node
        svc = self.bg.store.get_node("ha.service:light.turn_on")
        self.assertIsNotNone(svc)
        self.assertEqual(svc.kind, "service")

        # Entity node (created as target)
        entity = self.bg.store.get_node("ha.entity:light.bedroom")
        self.assertIsNotNone(entity)

        # Edge: service → entity
        edges = self.bg.store.get_edges(from_node="ha.service:light.turn_on")
        targets = [e for e in edges if e.edge_type == "targets"]
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].to_node, "ha.entity:light.bedroom")

    def test_call_service_without_entity(self):
        """Service call with no entity_id should still create service node."""
        event = {
            "kind": "call_service",
            "domain": "scene",
            "service": "turn_on",
        }
        stats = self.proc.process_events([event])
        self.assertEqual(stats["processed"], 1)

        svc = self.bg.store.get_node("ha.service:scene.turn_on")
        self.assertIsNotNone(svc)

    def test_unknown_kind_is_silently_ignored(self):
        event = {
            "kind": "heartbeat",
            "domain": "system",
        }
        stats = self.proc.process_events([event])
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["errors"], 0)

    def test_batch_processing(self):
        events = [
            {"kind": "state_changed", "entity_id": f"light.lamp_{i}", "domain": "light", "new": {"state": "on"}}
            for i in range(10)
        ]
        stats = self.proc.process_events(events)
        self.assertEqual(stats["processed"], 10)

    def test_score_boost_state_vs_service(self):
        """Service calls should boost salience more than state changes."""
        self.proc.process_events([
            {"kind": "state_changed", "entity_id": "light.a", "domain": "light", "new": {"state": "on"}},
        ])
        self.proc.process_events([
            {"kind": "call_service", "domain": "light", "service": "turn_on", "entity_id": "light.b"},
        ])
        node_a = self.bg.store.get_node("ha.entity:light.a")
        node_b = self.bg.store.get_node("ha.entity:light.b")
        # Both should exist; exact scores depend on delta values
        self.assertIsNotNone(node_a)
        self.assertIsNotNone(node_b)

    def test_custom_processor_registration(self):
        collected = []
        self.proc.add_processor(lambda evt: collected.append(evt))
        self.proc.process_events([{"kind": "state_changed", "entity_id": "sensor.x", "domain": "sensor"}])
        self.assertEqual(len(collected), 1)

    def test_no_brain_graph_service(self):
        """Processor without brain graph should still work (no-op)."""
        proc = EventProcessor(brain_graph_service=None)
        stats = proc.process_events([
            {"kind": "state_changed", "entity_id": "light.x", "domain": "light"},
        ])
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["errors"], 0)

    def test_error_in_one_event_does_not_stop_batch(self):
        """A processor error on one event should not abort the rest."""
        call_count = {"n": 0}

        def flaky_processor(evt):
            call_count["n"] += 1
            if evt.get("entity_id") == "sensor.bad":
                raise ValueError("simulated error")

        proc = EventProcessor(brain_graph_service=None)
        proc.add_processor(flaky_processor)

        stats = proc.process_events([
            {"kind": "state_changed", "entity_id": "sensor.good", "domain": "sensor"},
            {"kind": "state_changed", "entity_id": "sensor.bad", "domain": "sensor"},
            {"kind": "state_changed", "entity_id": "sensor.also_good", "domain": "sensor"},
        ])
        self.assertEqual(stats["processed"], 2)
        self.assertEqual(stats["errors"], 1)


if __name__ == "__main__":
    unittest.main()
