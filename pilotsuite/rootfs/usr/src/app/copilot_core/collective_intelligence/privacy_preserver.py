"""Privacy-Preserving Patterns for Collective Intelligence.

Implements:
- Differential Privacy with Gaussian noise
- Local Privacy Budget tracking
- Privacy-Aware Aggregation
"""

import math
import numpy as np
from typing import Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class PrivacyBudget:
    """Tracks privacy budget for a single node."""
    node_id: str
    epsilon: float  # Current privacy budget
    delta: float    # Privacy failure probability
    max_epsilon: float  # Maximum allowed epsilon
    max_delta: float    # Maximum allowed delta
    updates_used: int = 0

    def consume(self, epsilon_used: float, delta_used: float = 0.0) -> bool:
        """Attempt to consume privacy budget. Returns True if successful."""
        if self.epsilon + epsilon_used <= self.max_epsilon:
            self.epsilon += epsilon_used
            self.delta = 1 - (1 - self.delta) * (1 - delta_used)
            self.updates_used += 1
            return True
        return False

    def remaining(self) -> float:
        """Get remaining epsilon budget."""
        return max(0.0, self.max_epsilon - self.epsilon)

    def can_update(self, epsilon_cost: float) -> bool:
        """Check if update can be performed with remaining budget."""
        return self.epsilon + epsilon_cost <= self.max_epsilon


class DifferentialPrivacy:
    """Differential privacy mechanisms for federated learning."""

    def __init__(self, epsilon: float = 1.0, delta: float = 1e-5):
        """
        Initialize DP mechanism.

        Args:
            epsilon: Privacy budget (lower = more privacy)
            delta: Privacy failure probability
        """
        self.epsilon = epsilon
        self.delta = delta

    def compute_noise_scale(self, sensitivity: float, epsilon: Optional[float] = None) -> float:
        """
        Compute noise scale for Gaussian mechanism.

        Args:
            sensitivity: L2 sensitivity of the query
            epsilon: Optional override for epsilon

        Returns:
            Noise scale (sigma)
        """
        eps = epsilon or self.epsilon
        # Gaussian mechanism: sigma = sensitivity * sqrt(2 * ln(1.25/delta)) / epsilon
        return sensitivity * math.sqrt(2 * math.log(1.25 / self.delta)) / eps

    def add_gaussian_noise(self, value: Union[float, np.ndarray], sensitivity: float, 
                           epsilon: Optional[float] = None) -> Union[float, np.ndarray]:
        """
        Add Gaussian noise to a value.

        Args:
            value: The value to anonymize
            sensitivity: L2 sensitivity
            epsilon: Optional override for epsilon

        Returns:
            Noisy value
        """
        sigma = self.compute_noise_scale(sensitivity, epsilon)
        if isinstance(value, np.ndarray):
            noise = np.random.normal(0, sigma, value.shape)
            return value + noise
        else:
            return value + np.random.normal(0, sigma)

    def compute_global_sensitivity(self, values: List[float]) -> float:
        """
        Compute L2 sensitivity from a set of values.

        Args:
            values: List of values

        Returns:
            L2 sensitivity
        """
        if len(values) < 2:
            return 0.0
        mean = np.mean(values)
        return math.sqrt(np.mean((np.array(values) - mean) ** 2))

    def clip_values(self, values: Union[List[float], np.ndarray], 
                   max_norm: float) -> np.ndarray:
        """
        Clip values to bounded norm.

        Args:
            values: Values to clip
            max_norm: Maximum allowed L2 norm

        Returns:
            Clipped values
        """
        arr = np.array(values)
        norm = np.linalg.norm(arr)
        if norm > max_norm:
            return arr * (max_norm / norm)
        return arr


class PrivacyAwareAggregator:
    """Aggregator with privacy budget tracking."""

    def __init__(self, global_epsilon: float = 1.0, global_delta: float = 1e-5,
                 max_updates_per_round: int = 100):
        """
        Initialize privacy-aware aggregator.

        Args:
            global_epsilon: Total privacy budget per round
            global_delta: Total delta budget per round
            max_updates_per_round: Maximum participants per round
        """
        self.dp = DifferentialPrivacy(global_epsilon, global_delta)
        self.max_updates = max_updates_per_round
        self.node_budgets: Dict[str, PrivacyBudget] = {}

    def register_node(self, node_id: str, max_epsilon: float = 1.0,
                     max_delta: float = 1e-5) -> PrivacyBudget:
        """Register a node with its privacy budget."""
        budget = PrivacyBudget(
            node_id=node_id,
            epsilon=0.0,
            delta=0.0,
            max_epsilon=max_epsilon,
            max_delta=max_delta
        )
        self.node_budgets[node_id] = budget
        return budget

    def check_node_budget(self, node_id: str, epsilon_cost: float) -> bool:
        """Check if node has sufficient budget."""
        if node_id not in self.node_budgets:
            return False
        return self.node_budgets[node_id].can_update(epsilon_cost)

    def aggregate_with_privacy(self, updates: List[Dict[str, float]],
                              target_epsilon: Optional[float] = None) -> Dict[str, float]:
        """
        Aggregate updates with differential privacy.

        Args:
            updates: List of update dictionaries
            target_epsilon: Optional target epsilon

        Returns:
            Privacy-preserving aggregated result
        """
        if not updates:
            return {}

        # Compute per-coordinate sensitivity
        sensitivity = self._compute_coordinate_sensitivity(updates)

        # Aggregate with noise
        result = {}
        keys = updates[0].keys()

        for key in keys:
            values = [u[key] for u in updates]
            mean_val = np.mean(values)
            noisy_val = self.dp.add_gaussian_noise(
                mean_val, sensitivity[key], target_epsilon
            )
            result[key] = float(noisy_val)

        return result

    def _compute_coordinate_sensitivity(self, updates: List[Dict[str, float]]) -> Dict[str, float]:
        """Compute sensitivity for each coordinate."""
        if len(updates) < 2:
            return {k: 0.0 for k in updates[0].keys()}

        keys = updates[0].keys()
        sensitivity = {}

        for key in keys:
            values = [u[key] for u in updates]
            sensitivity[key] = self.dp.compute_global_sensitivity(values)

        return sensitivity

    def get_remaining_budget(self, node_id: str) -> float:
        """Get remaining budget for a node."""
        if node_id in self.node_budgets:
            return self.node_budgets[node_id].remaining()
        return 0.0
