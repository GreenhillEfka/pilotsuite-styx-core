"""Model Aggregation Module."""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import numpy as np

from .models import ModelUpdate, AggregatedModel, AggregationMethod


class ModelAggregator:
    """
    Handles model aggregation with versioning and quality tracking.

    Features:
    - Multiple aggregation strategies
    - Model versioning
    - Quality assessment
    - Backup/restore mechanisms
    """

    def __init__(self, default_method: AggregationMethod = AggregationMethod.FEDERATED_AVERAGING):
        """Initialize model aggregator."""
        self.default_method = default_method
        self.aggregated_models: Dict[str, AggregatedModel] = {}
        self.model_versions: List[str] = []
        self.quality_scores: Dict[str, float] = {}

    def aggregate(self, updates: List[ModelUpdate],
                 method: Optional[AggregationMethod] = None,
                 weights: Optional[Dict[str, float]] = None) -> Optional[AggregatedModel]:
        """
        Aggregate model updates.

        Args:
            updates: List of model updates
            method: Aggregation method (uses default if None)
            weights: Optional per-update weights

        Returns:
            Aggregated model or None if no updates
        """
        if not updates:
            return None

        method = method or self.default_method

        # Filter valid updates
        valid_updates = [u for u in updates if u.weights]

        if not valid_updates:
            return None

        # Perform aggregation
        aggregated_weights = self._aggregate_weights(
            valid_updates, method, weights
        )

        # Aggregate metrics
        aggregated_metrics = self._aggregate_metrics(valid_updates)

        # Determine version
        model_version = self._generate_version(
            valid_updates, method, aggregated_metrics
        )

        aggregated = AggregatedModel(
            model_version=model_version,
            weights=aggregated_weights,
            aggregation_method=method,
            participants=[u.node_id for u in valid_updates],
            metrics=aggregated_metrics
        )

        # Store model
        self.aggregated_models[model_version] = aggregated
        if model_version not in self.model_versions:
            self.model_versions.append(model_version)

        return aggregated

    def _aggregate_weights(self, updates: List[ModelUpdate],
                          method: AggregationMethod,
                          weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Aggregate model weights."""
        # Collect all weight keys
        weight_keys = set()
        for update in updates:
            weight_keys.update(update.weights.keys())

        aggregated = {}

        for key in weight_keys:
            values = []
            update_weights = []

            for update in updates:
                if key in update.weights:
                    val = update.weights[key]
                    if isinstance(val, (int, float)):
                        values.append(val)
                        update_weights.append(1.0)
                    elif isinstance(val, list):
                        values.extend(val)
                        update_weights.extend([1.0] * len(val))

            if values:
                aggregated[key] = self._aggregate_single_weight(
                    values, update_weights, method
                )

        return aggregated

    def _aggregate_single_weight(self, values: List[float],
                                 weights: List[float],
                                 method: AggregationMethod) -> float:
        """Aggregate a single weight value."""
        if not values:
            return 0.0

        if method == AggregationMethod.FEDERATED_AVERAGING:
            return np.mean(values)
        elif method == AggregationMethod.FEDERATED_MEDIAN:
            return np.median(values)
        elif method == AggregationMethod.FEDERATED_TRIMMED_MEAN:
            sorted_vals = sorted(values)
            trim = len(sorted_vals) // 10
            if trim > 0 and len(sorted_vals) > 2 * trim:
                return np.mean(sorted_vals[trim:-trim])
            return np.mean(values)
        elif method == AggregationMethod.WEIGHTED_AVERAGE:
            values_arr = np.array(values)
            weights_arr = np.array(weights)
            weights_arr = weights_arr / weights_arr.sum()
            return float(np.sum(values_arr * weights_arr))

        return np.mean(values)

    def _aggregate_metrics(self, updates: List[ModelUpdate]) -> Dict[str, float]:
        """Aggregate metrics from updates."""
        if not updates:
            return {}

        # Collect all metric keys
        metric_keys = set()
        for update in updates:
            metric_keys.update(update.metrics.keys())

        aggregated = {}

        for key in metric_keys:
            values = [u.metrics[key] for u in updates if key in u.metrics]
            if values:
                aggregated[key] = float(np.mean(values))

        return aggregated

    def _generate_version(self, updates: List[ModelUpdate],
                         method: AggregationMethod,
                         metrics: Dict[str, float]) -> str:
        """Generate model version string."""
        # Use timestamp as version base
        base_version = f"v{int(updates[0].timestamp)}"

        # Add method suffix
        method_suffix = method.value.replace("_", "-")

        # Add quality indicator
        quality = self._compute_quality(metrics)
        quality_suffix = f"-q{quality:.2f}"

        return f"{base_version}-{method_suffix}{quality_suffix}"

    def _compute_quality(self, metrics: Dict[str, float]) -> float:
        """Compute quality score from metrics."""
        if not metrics:
            return 0.5

        # Combine metrics into single score
        # Adjust weights based on metric type
        score = 0.0
        weight_sum = 0.0

        for key, value in metrics.items():
            if "accuracy" in key.lower():
                score += value * 1.0
                weight_sum += 1.0
            elif "loss" in key.lower():
                # Normalize loss to 0-1 range (assuming sigmoid-like behavior)
                normalized = 1.0 / (1.0 + np.exp(-value + 1))
                score += (1 - normalized) * 1.0
                weight_sum += 1.0
            elif "metric" in key.lower() or "score" in key.lower():
                score += value * 1.0
                weight_sum += 1.0

        return score / weight_sum if weight_sum > 0 else 0.5

    def get_model(self, version: str) -> Optional[AggregatedModel]:
        """Get model by version."""
        return self.aggregated_models.get(version)

    def get_latest_model(self) -> Optional[AggregatedModel]:
        """Get the most recent model."""
        if not self.model_versions:
            return None
        latest_version = self.model_versions[-1]
        return self.aggregated_models.get(latest_version)

    def list_versions(self) -> List[str]:
        """List all model versions."""
        return self.model_versions.copy()

    def restore_model(self, version: str) -> bool:
        """Restore model to a previous version."""
        if version in self.aggregated_models:
            model = self.aggregated_models[version]
            self.model_versions.append(version)
            return True
        return False

    def get_quality_history(self) -> List[Tuple[str, float]]:
        """Get quality history."""
        return [
            (v, self._compute_quality(self.aggregated_models[v].metrics))
            for v in self.model_versions
        ]

    def get_participant_stats(self) -> Dict[str, int]:
        """Get participation stats per node."""
        stats = {}
        for model in self.aggregated_models.values():
            for node_id in model.participants:
                stats[node_id] = stats.get(node_id, 0) + 1
        return stats
