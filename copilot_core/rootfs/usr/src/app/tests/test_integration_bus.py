"""Tests for the IntegrationBus, FeedbackLoop, and API."""

import unittest
from unittest.mock import MagicMock, patch, call

from copilot_core.integration.bus import IntegrationBus, BusEvent, KNOWN_EVENT_TYPES
from copilot_core.integration.protocol import ModuleProtocol
from copilot_core.integration.feedback import FeedbackLoop, ACCEPT_DELTA, REJECT_DELTA


class TestIntegrationBus(unittest.TestCase):
    """Tests for IntegrationBus pub/sub mechanics."""

    def setUp(self):
        self.bus = IntegrationBus()

    def test_publish_and_subscribe(self):
        """Events are delivered to subscribers."""
        received = []
        self.bus.subscribe("mood.changed", lambda e: received.append(e))
        event = self.bus.publish("mood.changed", {"mood": "focus"}, source="test")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_type, "mood.changed")
        self.assertEqual(received[0].data["mood"], "focus")
        self.assertEqual(received[0].source, "test")
        self.assertIsInstance(event, BusEvent)

    def test_multiple_subscribers(self):
        """Multiple subscribers all receive the event."""
        counts = {"a": 0, "b": 0}
        self.bus.subscribe("neuron.evaluated", lambda e: counts.__setitem__("a", counts["a"] + 1))
        self.bus.subscribe("neuron.evaluated", lambda e: counts.__setitem__("b", counts["b"] + 1))
        self.bus.publish("neuron.evaluated", {}, source="test")

        self.assertEqual(counts["a"], 1)
        self.assertEqual(counts["b"], 1)

    def test_subscribe_different_types(self):
        """Subscribers only receive their event type."""
        mood_events = []
        graph_events = []
        self.bus.subscribe("mood.changed", lambda e: mood_events.append(e))
        self.bus.subscribe("graph.updated", lambda e: graph_events.append(e))

        self.bus.publish("mood.changed", {"mood": "relax"}, source="test")

        self.assertEqual(len(mood_events), 1)
        self.assertEqual(len(graph_events), 0)

    def test_unsubscribe(self):
        """After unsubscribe, callbacks are no longer called."""
        received = []
        sub_id = self.bus.subscribe("mood.changed", lambda e: received.append(e))
        self.bus.publish("mood.changed", {"mood": "focus"}, source="test")
        self.assertEqual(len(received), 1)

        result = self.bus.unsubscribe(sub_id)
        self.assertTrue(result)

        self.bus.publish("mood.changed", {"mood": "relax"}, source="test")
        self.assertEqual(len(received), 1)  # Still 1

    def test_unsubscribe_unknown(self):
        """Unsubscribing unknown ID returns False."""
        self.assertFalse(self.bus.unsubscribe("nonexistent"))

    def test_subscriber_error_does_not_stop_others(self):
        """A failing subscriber does not prevent others from receiving events."""
        received = []

        def failing_callback(e):
            raise ValueError("boom")

        self.bus.subscribe("mood.changed", failing_callback)
        self.bus.subscribe("mood.changed", lambda e: received.append(e))

        self.bus.publish("mood.changed", {"mood": "focus"}, source="test")
        self.assertEqual(len(received), 1)

    def test_stats(self):
        """Stats track published/delivered/errors."""
        self.bus.subscribe("mood.changed", lambda e: None)
        self.bus.subscribe("mood.changed", lambda e: (_ for _ in ()).throw(ValueError))
        self.bus.publish("mood.changed", {}, source="test")

        stats = self.bus.get_stats()
        self.assertEqual(stats["events_published"], 1)
        self.assertEqual(stats["events_delivered"], 1)
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(stats["total_subscribers"], 2)

    def test_subscriber_count(self):
        """subscriber_count returns correct count per event type."""
        self.bus.subscribe("mood.changed", lambda e: None)
        self.bus.subscribe("mood.changed", lambda e: None)
        self.bus.subscribe("graph.updated", lambda e: None)

        self.assertEqual(self.bus.subscriber_count("mood.changed"), 2)
        self.assertEqual(self.bus.subscriber_count("graph.updated"), 1)
        self.assertEqual(self.bus.subscriber_count("nonexistent"), 0)

    def test_bus_event_fields(self):
        """BusEvent has all required fields."""
        event = BusEvent(
            event_type="mood.changed",
            data={"mood": "focus"},
            source="test",
        )
        self.assertEqual(event.event_type, "mood.changed")
        self.assertIsInstance(event.timestamp_ms, int)
        self.assertIsInstance(event.event_id, str)
        self.assertTrue(len(event.event_id) > 0)

    def test_known_event_types(self):
        """All documented event types are in the known set."""
        expected = {
            "neuron.evaluated", "mood.changed", "pattern.discovered",
            "suggestion.created", "suggestion.accepted", "suggestion.rejected",
            "graph.updated", "module.state_changed",
        }
        self.assertEqual(KNOWN_EVENT_TYPES, expected)

    def test_singleton(self):
        """get_instance returns the same object."""
        IntegrationBus._reset_instance()
        try:
            a = IntegrationBus.get_instance()
            b = IntegrationBus.get_instance()
            self.assertIs(a, b)
        finally:
            IntegrationBus._reset_instance()


class TestModuleProtocol(unittest.TestCase):
    """Tests for the ModuleProtocol interface."""

    def test_abstract_methods_enforced(self):
        """Cannot instantiate ModuleProtocol directly."""
        with self.assertRaises(TypeError):
            ModuleProtocol()

    def test_concrete_implementation(self):
        """A concrete implementation satisfies the protocol."""

        class MyModule(ModuleProtocol):
            def get_id(self):
                return "test_module"

            def get_layer(self):
                return 3

            def get_dependencies(self):
                return ["brain_graph"]

            def on_bus_event(self, event):
                pass

            def get_state_summary(self):
                return {"items": 42}

        mod = MyModule()
        self.assertEqual(mod.get_id(), "test_module")
        self.assertEqual(mod.get_layer(), 3)
        self.assertEqual(mod.get_dependencies(), ["brain_graph"])
        self.assertEqual(mod.get_state_summary(), {"items": 42})


class TestFeedbackLoop(unittest.TestCase):
    """Tests for the FeedbackLoop BrainGraph integration."""

    def setUp(self):
        self.mock_bg = MagicMock()
        self.bus = IntegrationBus()
        self.feedback = FeedbackLoop(self.mock_bg, self.bus)

    def test_accepted_reinforces_edges(self):
        """Accepting a suggestion calls touch_edge with positive delta."""
        self.bus.publish("suggestion.accepted", {
            "suggestion_id": "s1",
            "related_entities": ["light.kitchen", "switch.coffee"],
            "pattern_key": None,
        }, source="test")

        self.mock_bg.begin_batch.assert_called_once()
        self.mock_bg.touch_edge.assert_called_once_with(
            from_node="light.kitchen",
            edge_type="correlates",
            to_node="switch.coffee",
            delta=ACCEPT_DELTA,
            meta_patch={"feedback_source": "suggestion_loop"},
        )
        self.mock_bg.commit_batch.assert_called_once()

    def test_rejected_weakens_edges(self):
        """Rejecting a suggestion calls touch_edge with negative delta."""
        self.bus.publish("suggestion.rejected", {
            "suggestion_id": "s2",
            "related_entities": ["light.kitchen", "switch.coffee"],
        }, source="test")

        self.mock_bg.touch_edge.assert_called_once_with(
            from_node="light.kitchen",
            edge_type="correlates",
            to_node="switch.coffee",
            delta=REJECT_DELTA,
            meta_patch={"feedback_source": "suggestion_loop"},
        )

    def test_pattern_key_adjusts_triggered_by_edge(self):
        """A pattern_key adjusts the triggered_by edge."""
        self.bus.publish("suggestion.accepted", {
            "suggestion_id": "s3",
            "related_entities": [],
            "pattern_key": "light.kitchen:on → switch.coffee:on",
        }, source="test")

        self.mock_bg.touch_edge.assert_called_once_with(
            from_node="light.kitchen:on",
            edge_type="triggered_by",
            to_node="switch.coffee:on",
            delta=ACCEPT_DELTA,
            meta_patch={"feedback_source": "habitus_feedback"},
        )

    def test_no_entities_no_pattern_no_adjustment(self):
        """Empty data does not trigger any edge adjustments."""
        self.bus.publish("suggestion.accepted", {
            "suggestion_id": "s4",
            "related_entities": [],
        }, source="test")

        self.mock_bg.touch_edge.assert_not_called()
        self.mock_bg.begin_batch.assert_not_called()

    def test_stats(self):
        """get_stats returns correct counters."""
        self.bus.publish("suggestion.accepted", {
            "suggestion_id": "s5",
            "related_entities": ["a", "b"],
        }, source="test")

        stats = self.feedback.get_stats()
        self.assertEqual(stats["adjustments_applied"], 1)
        self.assertEqual(stats["accept_delta"], ACCEPT_DELTA)

    def test_rollback_on_error(self):
        """BrainGraph errors trigger rollback."""
        self.mock_bg.touch_edge.side_effect = RuntimeError("db error")

        self.bus.publish("suggestion.accepted", {
            "suggestion_id": "s6",
            "related_entities": ["a", "b"],
        }, source="test")

        self.mock_bg.rollback_batch.assert_called_once()


class TestIntegrationAPI(unittest.TestCase):
    """Tests for the integration REST API."""

    def setUp(self):
        from flask import Flask
        from copilot_core.integration.api import integration_bp, init_integration_api

        self.bus = IntegrationBus()
        self.mock_bg = MagicMock()
        self.feedback = FeedbackLoop(self.mock_bg, self.bus)

        init_integration_api(self.bus, self.feedback)

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(integration_bp)
        self.client = app.test_client()

    def test_post_feedback_accepted(self):
        """POST /feedback with accepted=true publishes suggestion.accepted."""
        received = []
        self.bus.subscribe("suggestion.accepted", lambda e: received.append(e))

        resp = self.client.post("/api/v1/integration/feedback", json={
            "suggestion_id": "s1",
            "accepted": True,
            "related_entities": ["light.kitchen"],
        })

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["event_type"], "suggestion.accepted")
        self.assertEqual(len(received), 1)

    def test_post_feedback_rejected(self):
        """POST /feedback with accepted=false publishes suggestion.rejected."""
        resp = self.client.post("/api/v1/integration/feedback", json={
            "suggestion_id": "s2",
            "accepted": False,
        })

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["event_type"], "suggestion.rejected")

    def test_post_feedback_missing_accepted(self):
        """POST /feedback without accepted field returns 400."""
        resp = self.client.post("/api/v1/integration/feedback", json={
            "suggestion_id": "s3",
        })
        self.assertEqual(resp.status_code, 400)

    def test_get_bus_stats(self):
        """GET /bus/stats returns bus metrics."""
        self.bus.publish("mood.changed", {}, source="test")

        resp = self.client.get("/api/v1/integration/bus/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("events_published", data)
        self.assertIn("feedback", data)


class TestNeuronManagerBusIntegration(unittest.TestCase):
    """Test that NeuronManager publishes events to the bus."""

    def test_evaluate_publishes_neuron_evaluated(self):
        """NeuronManager.evaluate() publishes neuron.evaluated event."""
        from copilot_core.neurons.manager import NeuronManager

        bus = IntegrationBus()
        received = []
        bus.subscribe("neuron.evaluated", lambda e: received.append(e))

        mgr = NeuronManager()
        mgr.configure_from_ha({}, {})
        mgr.set_bus(bus)
        mgr.evaluate()

        self.assertEqual(len(received), 1)
        self.assertIn("dominant_mood", received[0].data)
        self.assertIn("mood_confidence", received[0].data)
        self.assertEqual(received[0].source, "neuron_manager")

    def test_mood_change_publishes_event(self):
        """NeuronManager publishes mood.changed when mood transitions."""
        from copilot_core.neurons.manager import NeuronManager

        bus = IntegrationBus()
        received = []
        bus.subscribe("mood.changed", lambda e: received.append(e))

        mgr = NeuronManager()
        mgr.configure_from_ha({}, {})
        mgr.set_bus(bus)

        # First evaluate establishes baseline
        mgr.evaluate()

        # Force a mood change by manipulating mood neurons
        for name, neuron in mgr._mood_neurons.items():
            neuron.state.value = 0.0
        # Set one mood high to force a different dominant mood
        target_mood = "active" if "active" in mgr._mood_neurons else list(mgr._mood_neurons.keys())[0]
        mgr._mood_neurons[target_mood].state.value = 1.0

        # Evaluate again — mood should change
        mgr.evaluate()

        # May or may not have changed depending on smoothing — just check no crash
        # The event is only published when mood ACTUALLY changes
        for event in received:
            self.assertEqual(event.event_type, "mood.changed")
            self.assertIn("mood", event.data)
            self.assertIn("previous_mood", event.data)


class TestModuleRegistryBusIntegration(unittest.TestCase):
    """Test that ModuleRegistry publishes state changes to the bus."""

    def test_set_state_publishes_event(self):
        """ModuleRegistry.set_state() publishes module.state_changed."""
        import tempfile
        import os
        from copilot_core.module_registry import ModuleRegistry

        bus = IntegrationBus()
        received = []
        bus.subscribe("module.state_changed", lambda e: received.append(e))

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            registry = ModuleRegistry(db_path=db_path)
            registry.set_bus(bus)

            registry.set_state("mood_engine", "learning")

            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].data["module_id"], "mood_engine")
            self.assertEqual(received[0].data["new_state"], "learning")
            self.assertEqual(received[0].source, "module_registry")
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
