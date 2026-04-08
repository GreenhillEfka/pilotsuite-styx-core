"""Collective Intelligence Service - Main coordinator."""

import hashlib
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .federated_learner import FederatedLearner
from .model_aggregator import ModelAggregator
from .privacy_preserver import DifferentialPrivacy, PrivacyAwareAggregator
from .knowledge_transfer import KnowledgeTransfer
from .models import (
    ModelUpdate, AggregatedModel, FederatedRound,
    KnowledgeItem, AggregationMethod
)


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
        }


class CollectiveIntelligenceService:
    """
    Main service coordinating all collective intelligence features.

    Provides:
    - Federated learning orchestration
    - Model aggregation pipeline
    - Privacy budget management
    - Cross-home knowledge sharing
    """

    def __init__(self):
        """Initialize the collective intelligence service."""
        # Core components
        self.learner = FederatedLearner()
        self.aggregator = ModelAggregator()
        self.privacy_manager = PrivacyAwareAggregator(
            global_epsilon=1.0, global_delta=1e-5
        )
        self.knowledge_transfer = KnowledgeTransfer()

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
            knowledge_transferred=0
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

    def get_status(self) -> CIStatus:
        """Get current system status."""
        return self._status

    def get_federated_round_history(self) -> List[FederatedRound]:
        """Get history of federated rounds."""
        return self.learner.get_round_history()

    def get_aggregated_models(self) -> Dict[str, AggregatedModel]:
        """Get all aggregated models."""
        return self.aggregator.aggregated_models

    def get_knowledge_base(self) -> Dict[str, KnowledgeItem]:
        """Get knowledge transfer base."""
        return self.knowledge_transfer.knowledge_base

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        return {
            "status": self._status.to_dict(),
            "federated_rounds": len(self.learner.rounds),
            "aggregated_models": len(self.aggregator.aggregated_models),
            "knowledge_base_size": len(self.knowledge_transfer.knowledge_base),
            "transfer_statistics": self.knowledge_transfer.get_statistics(),
        }

    def save_state(self, path: str) -> bool:
        """Save system state to file."""
        try:
            import json
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
            import json
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

            return True
        except Exception:
            return False
