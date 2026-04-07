"""Tests for Hebbian Learning engine."""

import unittest
import tempfile
import os

from copilot_core.neurons.learning import (
    HebbianLearning,
    WeightUpdate,
    DEFAULT_LEARNING_RATE,
    DEFAULT_WEIGHT_DECAY,
    DEFAULT_MAX_WEIGHT,
    DEFAULT_MIN_WEIGHT,
)


class TestHebbianLearning(unittest.TestCase):
    """Tests for HebbianLearning weight updates."""

    def setUp(self):
        self.topology = [
            ("context.presence", "state.energy_level", 0.3),
            ("state.energy_level", "mood.focus", 0.3),
            ("state.stress_index", "mood.relax", -0.4),
        ]
        self.learner = HebbianLearning(self.topology)

    def test_initial_weights(self):
        """Weights start at topology values."""
        self.assertEqual(
            self.learner.get_weight("context.presence", "state.energy_level"),
            0.3,
        )
        self.assertEqual(
            self.learner.get_weight("state.stress_index", "mood.relax"),
            -0.4,
        )

    def test_unknown_synapse_returns_none(self):
        """get_weight for non-existent synapse returns None."""
        self.assertIsNone(self.learner.get_weight("foo", "bar"))

    def test_co_activation_increases_weight(self):
        """When both pre and post fire high, weight increases."""
        values = {
            "context.presence": 0.9,
            "state.energy_level": 0.8,
            "mood.focus": 0.7,
            "state.stress_index": 0.0,
            "mood.relax": 0.0,
        }

        updates = self.learner.update_weights(values)
        self.assertGreater(len(updates), 0)

        # presence→energy should increase (both high)
        w = self.learner.get_weight("context.presence", "state.energy_level")
        self.assertGreater(w, 0.3)

    def test_no_coactivation_decays_weight(self):
        """When neurons don't fire together, weight decays toward 0."""
        values = {
            "context.presence": 0.0,
            "state.energy_level": 0.0,
            "mood.focus": 0.0,
            "state.stress_index": 0.0,
            "mood.relax": 0.0,
        }

        # Run many updates to see decay
        for _ in range(100):
            self.learner.update_weights(values)

        w = self.learner.get_weight("context.presence", "state.energy_level")
        # Weight should decay toward 0 from 0.3
        self.assertLess(abs(w), 0.3)

    def test_weight_clamped_to_max(self):
        """Weights never exceed MAX_WEIGHT."""
        # Set high learning rate for quick convergence
        learner = HebbianLearning(self.topology, learning_rate=1.0)
        values = {
            "context.presence": 1.0,
            "state.energy_level": 1.0,
            "mood.focus": 1.0,
            "state.stress_index": 1.0,
            "mood.relax": 1.0,
        }

        for _ in range(1000):
            learner.update_weights(values)

        for key, w in learner.get_all_weights().items():
            self.assertLessEqual(w, DEFAULT_MAX_WEIGHT)
            self.assertGreaterEqual(w, DEFAULT_MIN_WEIGHT)

    def test_convergence_with_repeated_patterns(self):
        """Weights converge when shown repeated co-activation patterns."""
        initial_w = self.learner.get_weight("context.presence", "state.energy_level")

        values = {
            "context.presence": 0.8,
            "state.energy_level": 0.7,
            "mood.focus": 0.0,
            "state.stress_index": 0.0,
            "mood.relax": 0.0,
        }

        # Run many iterations
        for _ in range(50):
            self.learner.update_weights(values)

        final_w = self.learner.get_weight("context.presence", "state.energy_level")
        self.assertNotEqual(initial_w, final_w)

    def test_feedback_accepted_reinforces(self):
        """apply_feedback with accepted=True increases weights."""
        initial_w = self.learner.get_weight("context.presence", "state.energy_level")

        updates = self.learner.apply_feedback(
            related_neurons=["context.presence", "state.energy_level"],
            accepted=True,
            strength=0.1,
        )

        self.assertEqual(len(updates), 1)
        new_w = self.learner.get_weight("context.presence", "state.energy_level")
        self.assertGreater(new_w, initial_w)

    def test_feedback_rejected_weakens(self):
        """apply_feedback with accepted=False decreases weights."""
        initial_w = self.learner.get_weight("context.presence", "state.energy_level")

        updates = self.learner.apply_feedback(
            related_neurons=["context.presence", "state.energy_level"],
            accepted=False,
            strength=0.1,
        )

        new_w = self.learner.get_weight("context.presence", "state.energy_level")
        self.assertLess(new_w, initial_w)

    def test_reset_to_base(self):
        """reset_to_base restores original weights."""
        values = {"context.presence": 1.0, "state.energy_level": 1.0,
                  "mood.focus": 0.0, "state.stress_index": 0.0, "mood.relax": 0.0}
        self.learner.update_weights(values)

        self.learner.reset_to_base()

        self.assertEqual(
            self.learner.get_weight("context.presence", "state.energy_level"),
            0.3,
        )

    def test_weight_drift_tracking(self):
        """get_weight_drift shows deviations from base."""
        values = {"context.presence": 0.9, "state.energy_level": 0.8,
                  "mood.focus": 0.0, "state.stress_index": 0.0, "mood.relax": 0.0}
        self.learner.update_weights(values)

        drift = self.learner.get_weight_drift()
        self.assertGreater(len(drift), 0)

    def test_stats(self):
        """get_stats returns valid metrics."""
        stats = self.learner.get_stats()
        self.assertEqual(stats["total_synapses"], 3)
        self.assertEqual(stats["total_updates"], 0)
        self.assertEqual(stats["learning_rate"], DEFAULT_LEARNING_RATE)


class TestHebbianPersistence(unittest.TestCase):
    """Tests for weight persistence."""

    def test_save_and_load(self):
        """Weights survive save/load cycle."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            topology = [("a", "b", 0.5)]
            learner1 = HebbianLearning(topology, persist_path=path)
            learner1.update_weights({"a": 0.9, "b": 0.8})
            w_after = learner1.get_weight("a", "b")
            learner1.save_weights()

            # Load in new instance
            learner2 = HebbianLearning(topology, persist_path=path)
            self.assertAlmostEqual(learner2.get_weight("a", "b"), w_after, places=6)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
