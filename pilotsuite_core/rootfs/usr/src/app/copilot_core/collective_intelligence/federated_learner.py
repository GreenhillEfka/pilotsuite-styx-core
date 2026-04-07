"""Federated Learning Core."""

import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import numpy as np

from .models import ModelUpdate, AggregatedModel, FederatedRound, AggregationMethod
from .privacy_preserver import DifferentialPrivacy, PrivacyAwareAggregator


class FederatedLearner:
    """
    Implements federated learning without data sharing.

    Each participating home trains locally and only shares
    model updates (weights), not raw data.
    """

    def __init__(self, global_model_version: str = "v1.0.0",
                 aggregation_method: AggregationMethod = AggregationMethod.FEDERATED_AVERAGING,
                 min_participants: int = 2):
        """
        Initialize federated learner.

        Args:
            global_model_version: Starting model version
            aggregation_method: How to aggregate updates
            min_participants: Minimum nodes required for aggregation
        """
        self.global_model_version = global_model_version
        self.aggregation_method = aggregation_method
        self.min_participants = min_participants
        self.global_weights: Dict[str, Any] = {}
        self.rounds: List[FederatedRound] = []
        self.active_rounds: Dict[str, FederatedRound] = {}

        # Privacy settings
        self.privacy_dp = DifferentialPrivacy(epsilon=1.0, delta=1e-5)
        self.privacy_aggregator = PrivacyAwareAggregator(
            global_epsilon=1.0, global_delta=1e-5
        )

    def start_round(self, round_id: Optional[str] = None) -> FederatedRound:
        """Start a new federated learning round."""
        if round_id is None:
            round_id = hashlib.sha256(
                f"round_{time.time()}".encode()
            ).hexdigest()[:16]

        round_obj = FederatedRound(
            round_id=round_id,
            model_version=self.global_model_version,
            participating_nodes=[],
            updates=[]
        )
        self.active_rounds[round_id] = round_obj
        return round_obj

    def submit_update(self, node_id: str, weights: Dict[str, Any],
                     metrics: Optional[Dict[str, float]] = None,
                     model_version: Optional[str] = None,
                     round_id: Optional[str] = None) -> Optional[ModelUpdate]:
        """
        Submit a local model update.

        Args:
            node_id: ID of the participating node
            weights: Model weights (dict)
            metrics: Optional metrics (loss, accuracy, etc.)
            model_version: Model version being updated
            round_id: Optional specific round ID (uses latest active if not specified)

        Returns:
            ModelUpdate if successful, None if min participants not met
        """
        if model_version is None:
            model_version = self.global_model_version

        # Check privacy budget
        if not self.privacy_aggregator.check_node_budget(node_id, 0.1):
            return None

        update = ModelUpdate(
            node_id=node_id,
            model_version=model_version,
            weights=weights,
            metrics=metrics or {},
            timestamp=time.time()
        )

        # Register update to specified round or latest active round
        if round_id:
            # Use specified round
            if round_id in self.active_rounds:
                active_round = self.active_rounds[round_id]
                if active_round.model_version == model_version:
                    active_round.updates.append(update)
                    if node_id not in active_round.participating_nodes:
                        active_round.participating_nodes.append(node_id)
        else:
            # Find latest active round for this model version
            for rid, active_round in self.active_rounds.items():
                if active_round.model_version == model_version:
                    active_round.updates.append(update)
                    if node_id not in active_round.participating_nodes:
                        active_round.participating_nodes.append(node_id)
                    break

        return update

    def aggregate(self, round_id: str) -> Optional[AggregatedModel]:
        """
        Aggregate updates in a round.

        Args:
            round_id: ID of the round to aggregate

        Returns:
            Aggregated model or None if insufficient participants
        """
        if round_id not in self.active_rounds:
            return None

        round_obj = self.active_rounds[round_id]

        if len(round_obj.updates) < self.min_participants:
            return None

        # Perform aggregation based on method
        aggregated = self._perform_aggregation(round_obj.updates)

        if aggregated:
            round_obj.complete(aggregated)
            self.rounds.append(round_obj)
            self.global_weights = aggregated.weights
            self.global_model_version = f"v{aggregated.timestamp:.0f}"

        return aggregated

    def _perform_aggregation(self, updates: List[ModelUpdate]) -> AggregatedModel:
        """Perform the actual aggregation based on configured method."""
        if not updates:
            return AggregatedModel(
                model_version=self.global_model_version,
                weights={},
                aggregation_method=self.aggregation_method,
                participants=[],
                metrics={}
            )

        # Extract all weight keys
        weight_keys = set()
        for update in updates:
            weight_keys.update(update.weights.keys())

        # Aggregate each weight
        aggregated_weights = {}
        aggregated_metrics = {}
        participant_ids = [u.node_id for u in updates]

        for key in weight_keys:
            values = []
            for update in updates:
                if key in update.weights:
                    val = update.weights[key]
                    if isinstance(val, (int, float)):
                        values.append(val)
                    elif isinstance(val, list):
                        values.extend(val)

            if values:
                aggregated_weights[key] = self._aggregate_values(values)

        # Aggregate metrics
        if updates:
            metric_keys = updates[0].metrics.keys()
            for key in metric_keys:
                values = [u.metrics[key] for u in updates if key in u.metrics]
                if values:
                    aggregated_metrics[key] = np.mean(values)

        return AggregatedModel(
            model_version=self.global_model_version,
            weights=aggregated_weights,
            aggregation_method=self.aggregation_method,
            participants=participant_ids,
            metrics=aggregated_metrics
        )

    def _aggregate_values(self, values: List[float]) -> float:
        """Aggregate a list of values using the configured method."""
        if not values:
            return 0.0

        if self.aggregation_method == AggregationMethod.FEDERATED_AVERAGING:
            return np.mean(values)
        elif self.aggregation_method == AggregationMethod.FEDERATED_MEDIAN:
            return np.median(values)
        elif self.aggregation_method == AggregationMethod.FEDERATED_TRIMMED_MEAN:
            # Trim 10% from each end
            sorted_vals = sorted(values)
            trim = len(sorted_vals) // 10
            if trim > 0:
                trimmed = sorted_vals[trim:-trim]
                return np.mean(trimmed) if trimmed else np.mean(values)
            return np.mean(values)
        elif self.aggregation_method == AggregationMethod.WEIGHTED_AVERAGE:
            # Weight by update ID hash (simplified)
            weights = np.array([
                float(hashlib.md5(u.encode()).hexdigest(), 16)
                for u in [str(v) for v in values]
            ])
            weights = weights / weights.sum()
            return np.sum(np.array(values) * weights)

        return np.mean(values)

    def get_global_model(self) -> Dict[str, Any]:
        """Get current global model weights."""
        return self.global_weights

    def get_round_history(self) -> List[FederatedRound]:
        """Get history of completed rounds."""
        return self.rounds

    def register_participant(self, node_id: str, max_epsilon: float = 1.0):
        """Register a new participant node."""
        self.privacy_aggregator.register_node(node_id, max_epsilon=max_epsilon)
