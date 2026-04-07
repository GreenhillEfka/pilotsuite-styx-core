#!/usr/bin/env python3
"""Tests for federated learning."""

import unittest
import time
from unittest.mock import patch, MagicMock

try:
    from copilot_core.collective_intelligence.federated_learner import FederatedLearner
    from copilot_core.collective_intelligence.models import (
        ModelUpdate, AggregatedModel, FederatedRound, AggregationMethod
    )
except ModuleNotFoundError:
    FederatedLearner = None


class TestFederatedLearner(unittest.TestCase):
    """Test FederatedLearner functionality."""

    def setUp(self):
        """Set up test fixtures."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        self.learner = FederatedLearner(
            global_model_version="v1.0.0",
            aggregation_method=AggregationMethod.FEDERATED_AVERAGING,
            min_participants=2
        )

    def test_learner_initialization(self):
        """Test learner initialization."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        self.assertEqual(self.learner.global_model_version, "v1.0.0")
        self.assertEqual(self.learner.aggregation_method, AggregationMethod.FEDERATED_AVERAGING)
        self.assertEqual(self.learner.min_participants, 2)

    def test_start_round(self):
        """Test starting a new federated round."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        round_obj = self.learner.start_round("test-round-1")
        
        self.assertIsNotNone(round_obj)
        self.assertEqual(round_obj.round_id, "test-round-1")
        self.assertEqual(round_obj.model_version, "v1.0.0")
        self.assertEqual(len(round_obj.participating_nodes), 0)
        self.assertEqual(len(round_obj.updates), 0)

    def test_start_round_auto_id(self):
        """Test starting round with auto-generated ID."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        round_obj = self.learner.start_round()
        
        self.assertIsNotNone(round_obj.round_id)
        self.assertIsInstance(round_obj.round_id, str)
        self.assertGreater(len(round_obj.round_id), 0)

    def test_submit_update(self):
        """Test submitting a model update."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        # Start a round first
        self.learner.start_round("round-1")
        
        # Register node for privacy budget
        self.learner.register_participant("node-1", max_epsilon=1.0)
        
        weights = {"layer1": [0.1, 0.2], "layer2": [0.3]}
        metrics = {"loss": 0.5, "accuracy": 0.8}
        
        update = self.learner.submit_update(
            node_id="node-1",
            weights=weights,
            metrics=metrics,
            model_version="v1.0.0"
        )
        
        self.assertIsNotNone(update)
        self.assertEqual(update.node_id, "node-1")
        self.assertEqual(update.model_version, "v1.0.0")
        self.assertEqual(update.weights, weights)
        self.assertEqual(update.metrics, metrics)

    def test_submit_update_budget_check(self):
        """Test that updates check privacy budget."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        self.learner.start_round("round-budget")
        
        # Simulate budget exhausted
        with patch.object(self.learner.privacy_aggregator, 'check_node_budget', return_value=False):
            update = self.learner.submit_update(
                node_id="node-broke",
                weights={"layer1": [0.1]},
                metrics={}
            )
            # Should return None when budget exhausted
            self.assertIsNone(update)

    def test_aggregate_round(self):
        """Test aggregating a round."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        round_id = "round-agg"
        self.learner.start_round(round_id)
        
        # Register nodes for privacy budget
        self.learner.register_participant("node-1", max_epsilon=1.0)
        self.learner.register_participant("node-2", max_epsilon=1.0)
        
        # Submit updates from multiple nodes
        weights1 = {"layer1": [0.1, 0.2], "layer2": [0.3]}
        weights2 = {"layer1": [0.2, 0.3], "layer2": [0.4]}
        
        self.learner.submit_update("node-1", weights1, {"loss": 0.5}, round_id=round_id)
        self.learner.submit_update("node-2", weights2, {"loss": 0.4}, round_id=round_id)
        
        # Aggregate
        result = self.learner.aggregate(round_id)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, AggregatedModel)
        self.assertEqual(len(result.participants), 2)

    def test_get_global_weights(self):
        """Test getting global model weights."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        # Initially should be empty
        weights = self.learner.get_global_model()
        self.assertIsInstance(weights, dict)


class TestModelUpdate(unittest.TestCase):
    """Test ModelUpdate model."""

    def test_model_update_creation(self):
        """Test creating a ModelUpdate."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        update = ModelUpdate(
            node_id="node-1",
            model_version="v1.0.0",
            weights={"layer1": [0.1, 0.2]},
            metrics={"loss": 0.5}
        )
        
        self.assertEqual(update.node_id, "node-1")
        self.assertEqual(update.model_version, "v1.0.0")
        self.assertEqual(update.weights["layer1"], [0.1, 0.2])
        self.assertEqual(update.metrics["loss"], 0.5)

    def test_model_update_to_dict(self):
        """Test ModelUpdate serialization."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        update = ModelUpdate(
            node_id="node-1",
            model_version="v1.0.0",
            weights={"layer1": [0.1]}
        )
        
        data = update.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["node_id"], "node-1")
        self.assertEqual(data["model_version"], "v1.0.0")

    def test_model_update_id(self):
        """Test update_id property."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        update = ModelUpdate(
            node_id="node-1",
            model_version="v1.0.0",
            weights={"layer1": [0.1]}
        )
        
        self.assertIsNotNone(update.update_id)
        self.assertIsInstance(update.update_id, str)


class TestAggregatedModel(unittest.TestCase):
    """Test AggregatedModel model."""

    def test_aggregated_model_creation(self):
        """Test creating an AggregatedModel."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        model = AggregatedModel(
            model_version="v1.0.0",
            weights={"layer1": [0.15]},
            aggregation_method=AggregationMethod.FEDERATED_AVERAGING,
            participants=["node-1", "node-2"],
            metrics={"avg_loss": 0.45}
        )
        
        self.assertEqual(model.model_version, "v1.0.0")
        self.assertEqual(len(model.participants), 2)

    def test_aggregated_model_to_dict(self):
        """Test AggregatedModel serialization."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        model = AggregatedModel(
            model_version="v1.0.0",
            weights={"layer1": [0.1]},
            aggregation_method=AggregationMethod.FEDERATED_AVERAGING,
            participants=["node-1"],
            metrics={}
        )
        
        data = model.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["model_version"], "v1.0.0")


class TestFederatedRound(unittest.TestCase):
    """Test FederatedRound model."""

    def test_federated_round_creation(self):
        """Test creating a FederatedRound."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        round_obj = FederatedRound(
            round_id="round-1",
            model_version="v1.0.0",
            participating_nodes=["node-1"],
            updates=[]
        )
        
        self.assertEqual(round_obj.round_id, "round-1")
        self.assertIsNone(round_obj.aggregated_model)
        self.assertIsNone(round_obj.round_duration)

    def test_federated_round_complete(self):
        """Test marking round as complete."""
        if FederatedLearner is None:
            self.skipTest("FederatedLearner not available")
        round_obj = FederatedRound(
            round_id="round-1",
            model_version="v1.0.0",
            participating_nodes=[],
            updates=[]
        )
        
        model = AggregatedModel(
            model_version="v1.0.0",
            weights={},
            aggregation_method=AggregationMethod.FEDERATED_AVERAGING,
            participants=[],
            metrics={}
        )
        
        round_obj.complete(model)
        
        self.assertIsNotNone(round_obj.aggregated_model)
        self.assertIsNotNone(round_obj.round_duration)


if __name__ == "__main__":
    unittest.main()
