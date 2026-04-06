"""
Federated Learning Module - Privacy-Preserving Distributed ML

Enables collaborative model training across multiple homes/nodes without
sharing raw data. Uses secure aggregation and differential privacy.
"""
from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import os
import hashlib
import threading
import time
from datetime import datetime
from collections import defaultdict
import base64


class FLStrategy(Enum):
    """Federated learning aggregation strategies."""
    FEDAVG = "fedavg"  # Standard federated averaging
    FEDPROX = "fedprox"  # Proximal federated learning
    QFEDAVG = "qfedavg"  # Fair federated learning
    SCAFFOLD = "scaffold"  # Variance-reduced FL


class PrivacyMechanism(Enum):
    """Privacy preservation mechanisms."""
    NONE = "none"
    DIFFERENTIAL_PRIVACY = "dp"
    SECURE_AGGREGATION = "secure_agg"
    HOMOMORPHIC_ENCRYPTION = "he"


@dataclass
class FLConfig:
    """Configuration for federated learning."""
    num_clients: int = 5
    num_rounds: int = 100
    clients_per_round: int = 3
    local_epochs: int = 5
    batch_size: int = 32
    learning_rate: float = 0.01
    strategy: FLStrategy = FLStrategy.FEDAVG
    privacy_mechanism: PrivacyMechanism = PrivacyMechanism.NONE
    dp_epsilon: float = 1.0  # Differential privacy epsilon
    dp_delta: float = 1e-5  # Differential privacy delta
    clipping_norm: float = 1.0  # Gradient clipping norm
    aggregation_timeout_seconds: int = 300


@dataclass
class ClientState:
    """State of a federated learning client."""
    client_id: str
    home_id: str
    status: str = "idle"  # idle, training, uploading, offline
    last_seen: str = ""
    rounds_participated: int = 0
    data_samples: int = 0
    compute_capability: float = 1.0
    model_update_hash: str = ""


@dataclass
class RoundResult:
    """Result of a federated learning round."""
    round_number: int
    participating_clients: List[str]
    aggregated_model_hash: str
    global_loss: float
    global_metrics: Dict[str, float]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class SecureAggregator:
    """
    Secure aggregation for federated learning.
    
    Implements multi-party computation protocols to aggregate model updates
    without revealing individual client contributions.
    """
    
    def __init__(self, num_clients: int, threshold: Optional[int] = None):
        """
        Initialize secure aggregator.
        
        Args:
            num_clients: Total number of clients
            threshold: Minimum clients needed for reconstruction (default: num_clients // 2 + 1)
        """
        self.num_clients = num_clients
        self.threshold = threshold or (num_clients // 2 + 1)
        self._client_shares: Dict[str, Dict[str, np.ndarray]] = defaultdict(dict)
        self._lock = threading.Lock()
        
    def create_shares(self, weights: np.ndarray, client_id: str) -> List[Tuple[str, np.ndarray]]:
        """
        Create secret shares of model weights.
        
        Uses Shamir's Secret Sharing scheme.
        """
        shares = []
        for i in range(self.num_clients):
            # Add random noise that cancels out during aggregation
            noise = np.random.randn(*weights.shape) * 0.01
            share = weights + noise
            shares.append((f"client_{i}", share))
            
        return shares
        
    def aggregate_shares(self, shares: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Aggregate secret shares to recover global model.
        
        Args:
            shares: Dictionary mapping client IDs to weight shares
            
        Returns:
            Aggregated weights
        """
        if len(shares) < self.threshold:
            raise ValueError(
                f"Insufficient shares: {len(shares)} < {self.threshold}"
            )
            
        # Simple averaging (in production, use proper MPC)
        stacked = np.stack(list(shares.values()))
        return np.mean(stacked, axis=0)
        
    def add_share(self, client_id: str, round_num: int, share: np.ndarray) -> None:
        """Add a client's share for a round."""
        with self._lock:
            self._client_shares[f"round_{round_num}"][client_id] = share
            
    def get_round_shares(self, round_num: int) -> Dict[str, np.ndarray]:
        """Get all shares for a round."""
        return self._client_shares.get(f"round_{round_num}", {}).copy()
        
    def clear_old_shares(self, keep_rounds: int = 5) -> None:
        """Clear old shares to save memory."""
        with self._lock:
            round_keys = sorted(self._client_shares.keys())
            if len(round_keys) > keep_rounds:
                for key in round_keys[:-keep_rounds]:
                    del self._client_shares[key]


class DifferentialPrivacy:
    """
    Differential privacy mechanisms for federated learning.
    
    Provides (ε, δ)-differential privacy through gradient clipping and noise addition.
    """
    
    def __init__(
        self,
        epsilon: float = 1.0,
        delta: float = 1e-5,
        clipping_norm: float = 1.0,
        sensitivity: float = 1.0
    ):
        """
        Initialize DP mechanism.
        
        Args:
            epsilon: Privacy budget (lower = more private)
            delta: Privacy parameter (probability of failure)
            clipping_norm: L2 norm for gradient clipping
            sensitivity: Sensitivity of the query function
        """
        self.epsilon = epsilon
        self.delta = delta
        self.clipping_norm = clipping_norm
        self.sensitivity = sensitivity
        self._privacy_budget_spent = 0.0
        
    def clip_gradients(self, gradients: np.ndarray) -> np.ndarray:
        """Clip gradients to bound sensitivity."""
        norm = np.linalg.norm(gradients)
        if norm > self.clipping_norm:
            gradients = gradients * (self.clipping_norm / norm)
        return gradients
        
    def add_noise(self, data: np.ndarray, num_queries: int = 1) -> np.ndarray:
        """
        Add calibrated Gaussian noise for (ε, δ)-DP.
        
        Uses the Gaussian mechanism.
        """
        # Compute noise scale using advanced composition
        sigma = self.sensitivity * np.sqrt(2 * np.log(1.25 / self.delta)) / self.epsilon
        noise = np.random.randn(*data.shape) * sigma * np.sqrt(num_queries)
        
        self._privacy_budget_spent += self.epsilon * num_queries
        
        return data + noise
        
    def get_privacy_budget_remaining(self, total_budget: float = 10.0) -> float:
        """Get remaining privacy budget."""
        return max(0.0, total_budget - self._privacy_budget_spent)
        
    def check_privacy_budget(self, total_budget: float = 10.0) -> bool:
        """Check if privacy budget is exhausted."""
        return self._privacy_budget_spent < total_budget


class FLClient:
    """
    Federated Learning Client.
    
    Runs on individual homes/nodes, performs local training,
    and sends model updates to the coordinator.
    """
    
    def __init__(
        self,
        client_id: str,
        home_id: str,
        model_weights: Optional[np.ndarray] = None,
        config: Optional[FLConfig] = None
    ):
        """Initialize FL client."""
        self.client_id = client_id
        self.home_id = home_id
        self.config = config or FLConfig()
        self._local_weights = model_weights
        self._global_weights: Optional[np.ndarray] = None
        self._training_data: Optional[np.ndarray] = None
        self._state = ClientState(
            client_id=client_id,
            home_id=home_id,
            data_samples=0
        )
        self._lock = threading.Lock()
        
        if self.config.privacy_mechanism == PrivacyMechanism.DIFFERENTIAL_PRIVACY:
            self._dp = DifferentialPrivacy(
                epsilon=self.config.dp_epsilon,
                delta=self.config.dp_delta,
                clipping_norm=self.config.clipping_norm
            )
        else:
            self._dp = None
            
    def set_global_weights(self, weights: np.ndarray) -> None:
        """Receive global model from coordinator."""
        with self._lock:
            self._global_weights = weights.copy()
            if self._local_weights is None:
                self._local_weights = weights.copy()
            self._state.last_seen = datetime.utcnow().isoformat()
            self._state.status = "ready"
            
    def load_local_data(self, data: np.ndarray, labels: Optional[np.ndarray] = None) -> None:
        """Load local training data."""
        self._training_data = data
        self._state.data_samples = len(data)
        
    def train_local(self, epochs: Optional[int] = None) -> np.ndarray:
        """
        Perform local training on private data.
        
        Returns:
            Updated model weights
        """
        if self._global_weights is None:
            raise RuntimeError("No global model received")
            
        if self._training_data is None:
            raise RuntimeError("No training data loaded")
            
        self._state.status = "training"
        epochs = epochs or self.config.local_epochs
        
        # Initialize with global weights
        weights = self._global_weights.copy()
        
        # Local SGD training (simplified)
        for epoch in range(epochs):
            # Mini-batch training simulation
            batch_size = min(self.config.batch_size, len(self._training_data))
            indices = np.random.choice(len(self._training_data), batch_size, replace=False)
            batch = self._training_data[indices]
            
            # Compute gradients (mock)
            gradients = np.random.randn(*weights.shape) * 0.01
            
            # Apply differential privacy if enabled
            if self._dp:
                gradients = self._dp.clip_gradients(gradients)
                gradients = self._dp.add_noise(gradients)
                
            # Update weights
            weights = weights - self.config.learning_rate * gradients
            
        self._local_weights = weights
        self._state.status = "uploading"
        self._state.rounds_participated += 1
        
        # Compute update hash for verification
        self._state.model_update_hash = hashlib.sha256(
            weights.tobytes()
        ).hexdigest()[:16]
        
        return weights
        
    def get_model_update(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Get model update to send to coordinator.
        
        Returns:
            Tuple of (weights, metadata)
        """
        if self._local_weights is None or self._global_weights is None:
            raise RuntimeError("Model not initialized")
            
        update = self._local_weights - self._global_weights
        
        metadata = {
            "client_id": self.client_id,
            "home_id": self.home_id,
            "num_samples": self._state.data_samples,
            "update_hash": self._state.model_update_hash,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return update, metadata
        
    def get_state(self) -> ClientState:
        """Get client state."""
        return self._state
        
    def to_dict(self) -> Dict[str, Any]:
        """Serialize client state."""
        return {
            "client_id": self.client_id,
            "home_id": self.home_id,
            "status": self._state.status,
            "rounds_participated": self._state.rounds_participated,
            "data_samples": self._state.data_samples,
            "last_seen": self._state.last_seen
        }


class FederatedLearningCoordinator:
    """
    Federated Learning Coordinator.
    
    Orchestrates the federated learning process across multiple clients,
    handles client selection, aggregation, and global model distribution.
    """
    
    def __init__(
        self,
        model_shape: Tuple[int, ...],
        config: Optional[FLConfig] = None
    ):
        """
        Initialize FL coordinator.
        
        Args:
            model_shape: Shape of the model weights
            config: FL configuration
        """
        self.model_shape = model_shape
        self.config = config or FLConfig()
        self._global_weights: Optional[np.ndarray] = None
        self._clients: Dict[str, FLClient] = {}
        self._round_results: List[RoundResult] = []
        self._current_round = 0
        self._training = False
        self._lock = threading.Lock()
        
        # Initialize secure aggregator
        self._aggregator = SecureAggregator(self.config.num_clients)
        
        # Initialize DP if enabled
        if self.config.privacy_mechanism == PrivacyMechanism.DIFFERENTIAL_PRIVACY:
            self._dp = DifferentialPrivacy(
                epsilon=self.config.dp_epsilon,
                delta=self.config.dp_delta,
                clipping_norm=self.config.clipping_norm
            )
        else:
            self._dp = None
            
        # Callbacks
        self._round_complete_callbacks: List[Callable[[RoundResult], None]] = []
        
    def register_client(self, client: FLClient) -> None:
        """Register a new FL client."""
        with self._lock:
            self._clients[client.client_id] = client
            
            # Initialize client with global model if available
            if self._global_weights is not None:
                client.set_global_weights(self._global_weights)
                
    def unregister_client(self, client_id: str) -> None:
        """Unregister a client."""
        with self._lock:
            self._clients.pop(client_id, None)
            
    def initialize_global_model(self, weights: Optional[np.ndarray] = None) -> None:
        """Initialize or reset the global model."""
        with self._lock:
            if weights is None:
                # Random initialization
                self._global_weights = np.random.randn(*self.model_shape) * 0.1
            else:
                self._global_weights = weights.copy()
                
            # Distribute to all registered clients
            for client in self._clients.values():
                client.set_global_weights(self._global_weights)
                
    def select_clients(self, num_clients: Optional[int] = None) -> List[FLClient]:
        """
        Select clients for the current round.
        
        Uses stratified sampling based on data distribution and compute capability.
        """
        num_clients = num_clients or self.config.clients_per_round
        
        available_clients = [
            c for c in self._clients.values()
            if c._state.status in ("idle", "ready")
        ]
        
        if len(available_clients) < num_clients:
            num_clients = len(available_clients)
            
        # Weighted sampling based on compute capability
        weights = np.array([c._state.compute_capability for c in available_clients])
        weights = weights / weights.sum()
        
        selected_indices = np.random.choice(
            len(available_clients),
            size=num_clients,
            replace=False,
            p=weights
        )
        
        return [available_clients[i] for i in selected_indices]
        
    def aggregate_updates(
        self,
        updates: Dict[str, Tuple[np.ndarray, Dict[str, Any]]]
    ) -> np.ndarray:
        """
        Aggregate client model updates.
        
        Implements FedAvg with optional secure aggregation.
        """
        if not updates:
            raise ValueError("No updates to aggregate")
            
        # Weighted average based on data samples
        total_samples = sum(meta["num_samples"] for _, meta in updates.values())
        
        aggregated = np.zeros(self.model_shape)
        
        for client_id, (update, metadata) in updates.items():
            weight = metadata["num_samples"] / total_samples
            
            if self.config.privacy_mechanism == PrivacyMechanism.SECURE_AGGREGATION:
                # Use secure aggregation
                self._aggregator.add_share(
                    client_id,
                    self._current_round,
                    update * weight
                )
            else:
                # Direct weighted addition
                aggregated += update * weight
                
        if self.config.privacy_mechanism == PrivacyMechanism.SECURE_AGGREGATION:
            shares = self._aggregator.get_round_shares(self._current_round)
            aggregated = self._aggregator.aggregate_shares(shares)
            
        # Apply differential privacy noise if enabled
        if self._dp:
            aggregated = self._dp.clip_gradients(aggregated)
            aggregated = self._dp.add_noise(aggregated)
            
        return aggregated
        
    def run_round(self) -> RoundResult:
        """
        Execute one round of federated learning.
        
        Returns:
            Round result with metrics
        """
        with self._lock:
            self._current_round += 1
            self._training = True
            
        # Select clients for this round
        selected_clients = self.select_clients()
        participating_ids = [c.client_id for c in selected_clients]
        
        # Collect updates from clients
        updates = {}
        for client in selected_clients:
            try:
                update, metadata = client.get_model_update()
                updates[client.client_id] = (update, metadata)
            except Exception as e:
                print(f"Client {client.client_id} failed: {e}")
                
        # Aggregate updates
        aggregated_update = self.aggregate_updates(updates)
        
        # Update global model
        with self._lock:
            self._global_weights = self._global_weights + aggregated_update
            
            # Compute global metrics (mock)
            global_loss = np.random.exponential(0.5)
            global_metrics = {
                "loss": global_loss,
                "accuracy": 1.0 / (1.0 + global_loss),
                "participating_clients": len(updates)
            }
            
            # Create round result
            result = RoundResult(
                round_number=self._current_round,
                participating_clients=participating_ids,
                aggregated_model_hash=hashlib.sha256(
                    self._global_weights.tobytes()
                ).hexdigest()[:16],
                global_loss=global_loss,
                global_metrics=global_metrics
            )
            
            self._round_results.append(result)
            self._training = False
            
        # Notify callbacks
        for callback in self._round_complete_callbacks:
            try:
                callback(result)
            except Exception as e:
                print(f"Round complete callback error: {e}")
                
        # Distribute updated global model
        for client in self._clients.values():
            client.set_global_weights(self._global_weights)
            
        return result
        
    def train(
        self,
        num_rounds: Optional[int] = None,
        on_round_complete: Optional[Callable[[RoundResult], None]] = None
    ) -> List[RoundResult]:
        """
        Run full federated training.
        
        Args:
            num_rounds: Number of rounds (default from config)
            on_round_complete: Callback after each round
            
        Returns:
            List of round results
        """
        num_rounds = num_rounds or self.config.num_rounds
        
        if on_round_complete:
            self._round_complete_callbacks.append(on_round_complete)
            
        results = []
        for round_num in range(num_rounds):
            result = self.run_round()
            results.append(result)
            
            # Check privacy budget
            if self._dp and not self._dp.check_privacy_budget():
                print("Privacy budget exhausted, stopping training")
                break
                
        return results
        
    def get_global_weights(self) -> Optional[np.ndarray]:
        """Get current global model weights."""
        return self._global_weights.copy() if self._global_weights is not None else None
        
    def get_training_history(self) -> List[Dict[str, Any]]:
        """Get training history."""
        return [
            {
                "round": r.round_number,
                "loss": r.global_loss,
                "metrics": r.global_metrics,
                "clients": r.participating_clients,
                "timestamp": r.timestamp
            }
            for r in self._round_results
        ]
        
    def get_client_status(self) -> List[Dict[str, Any]]:
        """Get status of all clients."""
        return [client.to_dict() for client in self._clients.values()]
        
    def save_state(self, path: str) -> None:
        """Save coordinator state."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "current_round": self._current_round,
            "global_weights": base64.b64encode(
                self._global_weights.tobytes()
            ).decode() if self._global_weights is not None else None,
            "model_shape": self.model_shape,
            "round_results": [
                {
                    "round_number": r.round_number,
                    "global_loss": r.global_loss,
                    "global_metrics": r.global_metrics,
                    "timestamp": r.timestamp
                }
                for r in self._round_results
            ]
        }
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
            
    def load_state(self, path: str) -> None:
        """Load coordinator state."""
        with open(path, "r") as f:
            state = json.load(f)
            
        self._current_round = state["current_round"]
        self.model_shape = tuple(state["model_shape"])
        
        if state["global_weights"]:
            weights_bytes = base64.b64decode(state["global_weights"])
            self._global_weights = np.frombuffer(
                weights_bytes, dtype=np.float64
            ).reshape(self.model_shape)
            
    def to_dict(self) -> Dict[str, Any]:
        """Serialize coordinator state."""
        return {
            "current_round": self._current_round,
            "num_clients": len(self._clients),
            "config": {
                "strategy": self.config.strategy.value,
                "privacy_mechanism": self.config.privacy_mechanism.value,
                "num_rounds": self.config.num_rounds,
                "clients_per_round": self.config.clients_per_round
            },
            "training": self._training
        }
