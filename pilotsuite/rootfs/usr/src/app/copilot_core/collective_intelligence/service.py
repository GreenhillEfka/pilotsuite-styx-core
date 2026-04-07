# Enhanced with features from pilotsuite-styx-ha
"""Collective Intelligence Service - Main coordinator.

Provides federated learning orchestration, model aggregation, privacy budget
management, cross-home knowledge sharing, model type registration, pattern
sharing with TTL, and differential privacy (Laplace noise).
"""

import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

import numpy as np

from .federated_learner import FederatedLearner
from .model_aggregator import ModelAggregator
from .privacy_preserver import DifferentialPrivacy, PrivacyAwareAggregator
from .knowledge_transfer import KnowledgeTransfer
from .models import (
    ModelUpdate, AggregatedModel, FederatedRound,
    KnowledgeItem, AggregationMethod
)

_LOGGER = logging.getLogger(__name__)

# Valid model types matching HA collective intelligence
VALID_MODEL_TYPES: Set[str] = {"habit", "anomaly", "preference", "energy"}

# Default pattern TTL in days
DEFAULT_PATTERN_TTL_DAYS = 30


@dataclass
class RegisteredModelType:
    """A registered local model type with accuracy tracking.

    Mirrors the HA LocalModel concept: each model type (habit, anomaly,
    preference, energy) is registered with its parameters, version, and
    accuracy metrics.
    """
    model_id: str
    model_type: str  # One of VALID_MODEL_TYPES
    version: int
    parameters: Dict[str, Any]
    accuracy: float
    sample_count: int
    last_updated: float
    checksum: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "model_type": self.model_type,
            "version": self.version,
            "parameters": self.parameters,
            "accuracy": self.accuracy,
            "sample_count": self.sample_count,
            "last_updated": self.last_updated,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegisteredModelType":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class SharedPattern:
    """Anonymized pattern shared with the collective.

    Mirrors the HA SharedPattern: contains anonymized weights with
    differential privacy applied, a confidence score, and a TTL-based
    expiration timestamp.
    """
    pattern_id: str
    pattern_type: str
    category: str
    anonymized_weights: Dict[str, float]
    metadata: Dict[str, Any]
    contributed_by: str  # Node/home ID (not user ID)
    confidence: float
    created_at: float
    expires_at: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "category": self.category,
            "anonymized_weights": self.anonymized_weights,
            "metadata": self.metadata,
            "contributed_by": self.contributed_by,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SharedPattern":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class CIStatus:
    """Current status of the collective intelligence system."""
    is_active: bool
    active_rounds: int
    completed_rounds: int
    total_updates: int
    participating_nodes: int
    aggregated_models: int
    last_round_time: Optional[float]
    privacy_epsilon_used: float
    knowledge_transferred: int
    registered_model_types: int = 0
    shared_patterns_count: int = 0
    expired_patterns_cleaned: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_active": self.is_active,
            "active_rounds": self.active_rounds,
            "completed_rounds": self.completed_rounds,
            "total_updates": self.total_updates,
            "participating_nodes": self.participating_nodes,
            "aggregated_models": self.aggregated_models,
            "last_round_time": self.last_round_time,
            "privacy_epsilon_used": self.privacy_epsilon_used,
            "knowledge_transferred": self.knowledge_transferred,
            "registered_model_types": self.registered_model_types,
            "shared_patterns_count": self.shared_patterns_count,
            "expired_patterns_cleaned": self.expired_patterns_cleaned,
        }


class CollectiveIntelligenceService:
    """
    Main service coordinating all collective intelligence features.

    Provides:
    - Federated learning orchestration
    - Model aggregation pipeline
    - Privacy budget management
    - Cross-home knowledge sharing
    - Model type registration (habit, anomaly, preference, energy)
    - Pattern sharing with TTL and differential privacy
    """

    def __init__(
        self,
        privacy_epsilon: float = 1.0,
        min_contribution_score: float = 0.5,
        pattern_ttl_days: int = DEFAULT_PATTERN_TTL_DAYS,
    ):
        """Initialize the collective intelligence service.

        Args:
            privacy_epsilon: Differential privacy parameter for Laplace noise
                             (lower = more private).
            min_contribution_score: Minimum confidence to share a pattern.
            pattern_ttl_days: How many days shared patterns remain valid.
        """
        # Core components (delegated sub-services)
        self.learner = FederatedLearner()
        self.aggregator = ModelAggregator()
        self.privacy_manager = PrivacyAwareAggregator(
            global_epsilon=privacy_epsilon, global_delta=1e-5
        )
        self.knowledge_transfer = KnowledgeTransfer()

        # --- Model type registration (from HA) ---
        self.registered_models: Dict[str, RegisteredModelType] = {}
        self.model_accuracy_history: Dict[str, List[float]] = {}

        # --- Pattern sharing (from HA) ---
        self.privacy_epsilon = privacy_epsilon
        self.min_contribution_score = min_contribution_score
        self.pattern_ttl_days = pattern_ttl_days
        self.shared_patterns: Dict[str, SharedPattern] = {}

        # System state
        self.is_active = False
        self._status = CIStatus(
            is_active=False,
            active_rounds=0,
            completed_rounds=0,
            total_updates=0,
            participating_nodes=0,
            aggregated_models=0,
            last_round_time=None,
            privacy_epsilon_used=0.0,
            knowledge_transferred=0,
            registered_model_types=0,
            shared_patterns_count=0,
            expired_patterns_cleaned=0,
        )

    def start(self):
        """Start the collective intelligence service."""
        self.is_active = True
        self._status.is_active = True
        self._status.last_round_time = time.time()

    def stop(self):
        """Stop the collective intelligence service."""
        self.is_active = False
        self._status.is_active = False

    def register_node(self, node_id: str, max_epsilon: float = 1.0) -> bool:
        """Register a new home node."""
        if not self.is_active:
            return False

        # Register for federated learning
        self.learner.register_participant(node_id, max_epsilon=max_epsilon)

        # Register for privacy management
        self.privacy_manager.register_node(node_id, max_epsilon=max_epsilon)

        # Update status
        self._status.participating_nodes += 1

        return True

    def submit_local_update(self, node_id: str, weights: Dict[str, Any],
                           metrics: Optional[Dict[str, float]] = None) -> Optional[ModelUpdate]:
        """Submit a local model update from a node."""
        if not self.is_active:
            return None

        update = self.learner.submit_update(node_id, weights, metrics)
        if update:
            self._status.total_updates += 1

        return update

    def start_federated_round(self) -> str:
        """Start a new federated learning round."""
        if not self.is_active:
            return ""

        round_obj = self.learner.start_round()
        self._status.active_rounds += 1
        return round_obj.round_id

    def execute_aggregation(self, round_id: str) -> Optional[AggregatedModel]:
        """Execute aggregation for a round."""
        if not self.is_active:
            return None

        aggregated = self.learner.aggregate(round_id)
        if aggregated:
            self._status.completed_rounds += 1
            self._status.active_rounds -= 1
            self._status.aggregated_models += 1
            self._status.last_round_time = time.time()

            # Update privacy usage
            self._status.privacy_epsilon_used = sum(
                budget.epsilon for budget in self.privacy_manager.node_budgets.values()
            )

        return aggregated

    def extract_knowledge(self, node_id: str, knowledge_type: str,
                         payload: Dict[str, Any],
                         confidence: float = 1.0) -> Optional[KnowledgeItem]:
        """Extract knowledge from a node for transfer."""
        if not self.is_active:
            return None

        return self.knowledge_transfer.extract_knowledge(
            node_id, knowledge_type, payload, confidence
        )

    def transfer_knowledge(self, knowledge_id: str,
                          target_node_id: str) -> bool:
        """Transfer knowledge to another node."""
        if not self.is_active:
            return False

        success = self.knowledge_transfer.transfer_knowledge(
            knowledge_id, target_node_id
        )

        if success:
            self._status.knowledge_transferred += 1

        return success

    # ------------------------------------------------------------------
    # Model type registration (ported from HA collective intelligence)
    # ------------------------------------------------------------------

    def register_model_type(
        self,
        model_id: str,
        model_type: str,
        parameters: Dict[str, Any],
    ) -> RegisteredModelType:
        """Register a local model type for federated learning.

        Args:
            model_id: Unique identifier for the model.
            model_type: One of "habit", "anomaly", "preference", "energy".
            parameters: Initial model parameters.

        Returns:
            The registered model type.

        Raises:
            ValueError: If model_type is not one of the valid types.
        """
        if model_type not in VALID_MODEL_TYPES:
            raise ValueError(
                f"Invalid model_type '{model_type}'. "
                f"Must be one of {sorted(VALID_MODEL_TYPES)}"
            )

        model = RegisteredModelType(
            model_id=model_id,
            model_type=model_type,
            version=1,
            parameters=parameters,
            accuracy=0.0,
            sample_count=0,
            last_updated=time.time(),
            checksum=self._compute_checksum(parameters),
        )

        self.registered_models[model_id] = model
        self.model_accuracy_history.setdefault(model_id, [])
        self._status.registered_model_types = len(self.registered_models)

        _LOGGER.info(
            "Registered model %s of type %s", model_id, model_type
        )
        return model

    def update_model_accuracy(
        self,
        model_id: str,
        parameters: Dict[str, Any],
        accuracy: float,
        sample_count: int,
    ) -> RegisteredModelType:
        """Update a registered model with new training results.

        Args:
            model_id: Model to update.
            parameters: New model parameters.
            accuracy: Current model accuracy (0.0 - 1.0).
            sample_count: Number of training samples used.

        Returns:
            The updated model.

        Raises:
            ValueError: If model_id is not registered.
        """
        if model_id not in self.registered_models:
            raise ValueError(f"Model {model_id} not registered")

        model = self.registered_models[model_id]
        model.parameters = parameters
        model.version += 1
        model.accuracy = accuracy
        model.sample_count = sample_count
        model.last_updated = time.time()
        model.checksum = self._compute_checksum(parameters)

        # Track accuracy history
        self.model_accuracy_history.setdefault(model_id, []).append(accuracy)

        _LOGGER.debug(
            "Updated model %s to version %d (accuracy=%.3f)",
            model_id, model.version, accuracy
        )
        return model

    def get_model_type(self, model_id: str) -> Optional[RegisteredModelType]:
        """Get a registered model by ID.

        Args:
            model_id: The model identifier.

        Returns:
            RegisteredModelType or None if not found.
        """
        return self.registered_models.get(model_id)

    def get_model_types_by_category(
        self, model_type: str
    ) -> List[RegisteredModelType]:
        """Get all registered models of a given type.

        Args:
            model_type: One of VALID_MODEL_TYPES.

        Returns:
            List of matching registered models.
        """
        return [
            m for m in self.registered_models.values()
            if m.model_type == model_type
        ]

    @staticmethod
    def _compute_checksum(parameters: Dict[str, Any]) -> str:
        """Compute SHA-256 checksum for model parameters."""
        param_str = json.dumps(parameters, sort_keys=True)
        return hashlib.sha256(param_str.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Pattern sharing with differential privacy (ported from HA)
    # ------------------------------------------------------------------

    def _apply_laplace_noise(
        self, weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply Laplace-mechanism differential privacy to weights.

        Uses the same approach as the HA integration: scale = 1/epsilon,
        independent Laplace noise per weight dimension.

        Args:
            weights: Original model weights.

        Returns:
            Privacy-enhanced weights with Laplace noise added.
        """
        if not self.privacy_epsilon or self.privacy_epsilon <= 0:
            return dict(weights)

        scale = 1.0 / self.privacy_epsilon
        noisy: Dict[str, float] = {}
        for key, value in weights.items():
            noise = float(np.random.laplace(0, scale))
            noisy[key] = value + noise
        return noisy

    def create_shared_pattern(
        self,
        source_node_id: str,
        pattern_type: str,
        category: str,
        weights: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
    ) -> Optional[SharedPattern]:
        """Create a shareable pattern with differential privacy.

        Applies Laplace noise to the weights and normalizes them before
        sharing. Only creates the pattern if confidence meets the minimum
        contribution threshold.

        Args:
            source_node_id: ID of the contributing node/home.
            pattern_type: Type of pattern (e.g. "habit", "energy").
            category: Pattern category (e.g. "lighting", "temperature").
            weights: Raw model weights to anonymize.
            metadata: Optional additional metadata.
            confidence: Pattern confidence score (0.0 - 1.0).

        Returns:
            SharedPattern if confidence meets threshold, None otherwise.
        """
        if confidence < self.min_contribution_score:
            _LOGGER.debug(
                "Pattern %s/%s below contribution threshold (%.2f < %.2f)",
                pattern_type, category, confidence,
                self.min_contribution_score
            )
            return None

        # Apply differential privacy (Laplace noise)
        private_weights = self._apply_laplace_noise(weights)

        # Normalize weights (L2 norm)
        if private_weights:
            values = np.array(list(private_weights.values()))
            norm = float(np.linalg.norm(values))
            if norm > 0:
                private_weights = {
                    k: v / norm for k, v in private_weights.items()
                }

        now = time.time()
        pattern_id = hashlib.sha256(
            f"{source_node_id}:{pattern_type}:{now}".encode()
        ).hexdigest()[:16]

        pattern = SharedPattern(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            category=category,
            anonymized_weights=private_weights,
            metadata=metadata or {},
            contributed_by=source_node_id,
            confidence=confidence,
            created_at=now,
            expires_at=now + (self.pattern_ttl_days * 86400),
        )

        self.shared_patterns[pattern_id] = pattern
        self._status.shared_patterns_count = len(self.shared_patterns)

        _LOGGER.info(
            "Created shared pattern %s (%s/%s) confidence=%.2f ttl=%dd",
            pattern_id, pattern_type, category, confidence,
            self.pattern_ttl_days
        )
        return pattern

    def receive_patterns(
        self,
        patterns: List[SharedPattern],
        own_node_id: Optional[str] = None,
    ) -> int:
        """Receive shared patterns from other nodes.

        Filters out expired patterns and patterns contributed by the
        receiving node itself. Only adds patterns not already known.

        Args:
            patterns: List of SharedPattern instances to ingest.
            own_node_id: Optional node ID to skip own patterns.

        Returns:
            Number of new patterns added.
        """
        now = time.time()
        added = 0

        for pattern in patterns:
            # Skip expired
            if pattern.expires_at <= now:
                continue
            # Skip own patterns
            if own_node_id and pattern.contributed_by == own_node_id:
                continue
            # Add if new
            if pattern.pattern_id not in self.shared_patterns:
                self.shared_patterns[pattern.pattern_id] = pattern
                added += 1

        if added > 0:
            self._status.shared_patterns_count = len(self.shared_patterns)
            _LOGGER.info("Received %d new patterns from collective", added)

        return added

    def get_patterns_by_type(
        self,
        pattern_type: str,
        category: Optional[str] = None,
    ) -> List[SharedPattern]:
        """Get non-expired patterns filtered by type and optional category.

        Args:
            pattern_type: Pattern type to filter on.
            category: Optional category filter.

        Returns:
            List of matching patterns, sorted by confidence descending.
        """
        now = time.time()
        results = []

        for pattern in self.shared_patterns.values():
            if pattern.expires_at <= now:
                continue
            if pattern.pattern_type != pattern_type:
                continue
            if category and pattern.category != category:
                continue
            results.append(pattern)

        results.sort(key=lambda p: p.confidence, reverse=True)
        return results

    def get_aggregate_for_type(
        self, pattern_type: str
    ) -> Dict[str, Any]:
        """Aggregate intelligence for a pattern type.

        Computes a confidence-weighted average of all non-expired patterns
        of the given type.

        Args:
            pattern_type: Pattern type to aggregate.

        Returns:
            Dict with aggregated weights, confidence, contributor list.
        """
        patterns = self.get_patterns_by_type(pattern_type)

        if not patterns:
            return {
                "pattern_type": pattern_type,
                "count": 0,
                "aggregated_weights": {},
                "average_confidence": 0.0,
                "contributors": [],
            }

        total_confidence = sum(p.confidence for p in patterns)
        aggregated_weights: Dict[str, float] = {}

        for pattern in patterns:
            weight = pattern.confidence / total_confidence
            for key, value in pattern.anonymized_weights.items():
                aggregated_weights[key] = (
                    aggregated_weights.get(key, 0.0) + value * weight
                )

        return {
            "pattern_type": pattern_type,
            "count": len(patterns),
            "aggregated_weights": aggregated_weights,
            "average_confidence": total_confidence / len(patterns),
            "contributors": list({p.contributed_by for p in patterns}),
        }

    # ------------------------------------------------------------------
    # Pattern TTL management (ported from HA)
    # ------------------------------------------------------------------

    def cleanup_expired_patterns(self) -> int:
        """Remove patterns whose TTL has expired.

        Returns:
            Number of expired patterns removed.
        """
        now = time.time()
        expired_ids = [
            pid for pid, p in self.shared_patterns.items()
            if p.expires_at <= now
        ]

        for pid in expired_ids:
            del self.shared_patterns[pid]

        if expired_ids:
            removed = len(expired_ids)
            self._status.expired_patterns_cleaned += removed
            self._status.shared_patterns_count = len(self.shared_patterns)
            _LOGGER.info("Cleaned up %d expired patterns", removed)
            return removed

        return 0

    def get_status(self) -> CIStatus:
        """Get current system status."""
        return self._status

    def get_federated_round_history(self) -> List[FederatedRound]:
        """Get history of federated rounds."""
        return self.learner.get_round_history()

    def get_aggregated_models(self) -> Dict[str, AggregatedModel]:
        """Get all aggregated models from completed rounds."""
        # Extract aggregated models from completed rounds
        models = {}
        for round_obj in self.learner.rounds:
            if round_obj.aggregated_model:
                models[round_obj.aggregated_model.model_version] = round_obj.aggregated_model
        return models

    def get_knowledge_base(self) -> Dict[str, KnowledgeItem]:
        """Get knowledge transfer base."""
        return self.knowledge_transfer.knowledge_base

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        # Build per-type pattern counts (non-expired only)
        now = time.time()
        pattern_type_counts: Dict[str, int] = {}
        for p in self.shared_patterns.values():
            if p.expires_at > now:
                pattern_type_counts[p.pattern_type] = (
                    pattern_type_counts.get(p.pattern_type, 0) + 1
                )

        # Build per-type model info
        model_type_info: Dict[str, Dict[str, Any]] = {}
        for m in self.registered_models.values():
            model_type_info[m.model_id] = {
                "type": m.model_type,
                "version": m.version,
                "accuracy": m.accuracy,
                "sample_count": m.sample_count,
            }

        return {
            "status": self._status.to_dict(),
            "federated_rounds": len(self.learner.rounds),
            "aggregated_models": len(self.aggregator.aggregated_models),
            "knowledge_base_size": len(self.knowledge_transfer.knowledge_base),
            "transfer_statistics": self.knowledge_transfer.get_statistics(),
            "registered_models": model_type_info,
            "shared_patterns": {
                "total": len(self.shared_patterns),
                "by_type": pattern_type_counts,
            },
            "privacy_epsilon": self.privacy_epsilon,
            "pattern_ttl_days": self.pattern_ttl_days,
        }

    def save_state(self, path: str) -> bool:
        """Save system state to file."""
        try:
            state = {
                "is_active": self.is_active,
                "status": self._status.to_dict(),
                "rounds": [r.to_dict() for r in self.learner.rounds],
                "aggregated_models": {
                    k: v.to_dict() for k, v in self.aggregator.aggregated_models.items()
                },
                "knowledge_base": {
                    k: v.to_dict() for k, v in self.knowledge_transfer.knowledge_base.items()
                },
                "registered_models": [
                    m.to_dict() for m in self.registered_models.values()
                ],
                "model_accuracy_history": self.model_accuracy_history,
                "shared_patterns": [
                    p.to_dict() for p in self.shared_patterns.values()
                ],
                "privacy_epsilon": self.privacy_epsilon,
                "pattern_ttl_days": self.pattern_ttl_days,
                "min_contribution_score": self.min_contribution_score,
                "timestamp": time.time(),
            }
            with open(path, "w") as f:
                json.dump(state, f, indent=2)
            return True
        except Exception:
            return False

    def load_state(self, path: str) -> bool:
        """Load system state from file."""
        try:
            with open(path, "r") as f:
                state = json.load(f)

            self.is_active = state.get("is_active", False)
            self._status.is_active = self.is_active

            # Load rounds
            self.learner.rounds = []
            for round_data in state.get("rounds", []):
                self.learner.rounds.append(FederatedRound(**round_data))

            # Load aggregated models
            self.aggregator.aggregated_models = {}
            for k, v in state.get("aggregated_models", {}).items():
                self.aggregator.aggregated_models[k] = AggregatedModel.from_dict(v)

            # Load knowledge base
            self.knowledge_transfer.knowledge_base = {}
            for k, v in state.get("knowledge_base", {}).items():
                self.knowledge_transfer.knowledge_base[k] = KnowledgeItem.from_dict(v)

            # Load registered model types
            self.registered_models = {}
            for model_data in state.get("registered_models", []):
                model = RegisteredModelType.from_dict(model_data)
                self.registered_models[model.model_id] = model
            self.model_accuracy_history = state.get(
                "model_accuracy_history", {}
            )
            self._status.registered_model_types = len(self.registered_models)

            # Load shared patterns (filter expired)
            self.shared_patterns = {}
            now = time.time()
            for pattern_data in state.get("shared_patterns", []):
                pattern = SharedPattern.from_dict(pattern_data)
                if pattern.expires_at > now:
                    self.shared_patterns[pattern.pattern_id] = pattern
            self._status.shared_patterns_count = len(self.shared_patterns)

            # Restore privacy/TTL settings
            self.privacy_epsilon = state.get(
                "privacy_epsilon", self.privacy_epsilon
            )
            self.pattern_ttl_days = state.get(
                "pattern_ttl_days", self.pattern_ttl_days
            )
            self.min_contribution_score = state.get(
                "min_contribution_score", self.min_contribution_score
            )

            return True
        except Exception:
            return False
