"""Advanced ML — Federated Learning, Model Optimization, AutoML."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class ModelOptimization(Enum):
    """Model optimization strategies."""
    QUANTIZATION = "quantization"
    PRUNING = "pruning"
    DISTILLATION = "distillation"
    NEURAL_ARCH_SEARCH = "nas"


@dataclass
class FederatedConfig:
    """Federated learning configuration."""
    num_clients: int = 5
    rounds: int = 10
    learning_rate: float = 0.01
    batch_size: int = 32
    privacy_epsilon: float = 1.0
    aggregation_method: str = "fedavg"


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    latency_ms: float
    memory_mb: float
    size_mb: float


class AdvancedMLEngine:
    """Advanced ML capabilities for PilotSuite."""

    def __init__(self):
        self._federated_config: Optional[FederatedConfig] = None
        self._model_registry: Dict[str, Dict] = {}
        self._optimization_history: List[Dict] = []
        self._automl_trials: Dict[str, Any] = {}

    def configure_federated_learning(self, config: FederatedConfig):
        """Configure federated learning for privacy-preserving training."""
        self._federated_config = config
        logger.info(f"Federated learning configured: {config.num_clients} clients, {config.rounds} rounds")
        
        # Initialize federated state
        self._federated_state = {
            "global_model": None,
            "client_updates": [],
            "round": 0,
            "aggregated_weights": None,
        }
        
        return self._federated_state

    def federated_aggregate(self, client_updates: List[Dict]) -> Dict[str, Any]:
        """Aggregate client updates using FedAvg."""
        if not self._federated_config:
            raise RuntimeError("Federated learning not configured")
        
        if not client_updates:
            return {"status": "no_updates", "weights": None}
        
        # FedAvg aggregation
        num_clients = len(client_updates)
        aggregated = {}
        
        # Average all weight updates
        for key in client_updates[0].get("weights", {}).keys():
            aggregated[key] = sum(
                client["weights"].get(key, 0) * client.get("samples", 1)
                for client in client_updates
            ) / sum(client.get("samples", 1) for client in client_updates)
        
        self._federated_state["global_model"] = aggregated
        self._federated_state["round"] += 1
        self._federated_state["aggregated_weights"] = aggregated
        
        logger.info(f"Federated round {self._federated_state['round']} complete")
        
        return {
            "status": "aggregated",
            "round": self._federated_state["round"],
            "weights": aggregated,
        }

    def add_differential_privacy(self, weights: Dict, epsilon: float = 1.0) -> Dict:
        """Add differential privacy noise to weights."""
        import random
        
        noisy_weights = {}
        scale = 1.0 / epsilon
        
        for key, value in weights.items():
            if isinstance(value, (int, float)):
                # Add Laplace noise
                noise = random.laplace(0, scale)
                noisy_weights[key] = value + noise
            else:
                noisy_weights[key] = value
        
        return noisy_weights

    def optimize_model(self, model_name: str, strategy: ModelOptimization) -> ModelMetrics:
        """Apply model optimization strategy."""
        logger.info(f"Optimizing {model_name} with {strategy.value}")
        
        # Simulated optimization results
        base_metrics = ModelMetrics(
            accuracy=0.92,
            precision=0.89,
            recall=0.91,
            f1_score=0.90,
            latency_ms=50.0,
            memory_mb=256.0,
            size_mb=100.0,
        )
        
        optimizations = {
            ModelOptimization.QUANTIZATION: {
                "size_reduction": 0.75,
                "latency_reduction": 0.60,
                "accuracy_loss": 0.02,
            },
            ModelOptimization.PRUNING: {
                "size_reduction": 0.50,
                "latency_reduction": 0.40,
                "accuracy_loss": 0.03,
            },
            ModelOptimization.DISTILLATION: {
                "size_reduction": 0.80,
                "latency_reduction": 0.70,
                "accuracy_loss": 0.05,
            },
            ModelOptimization.NEURAL_ARCH_SEARCH: {
                "size_reduction": 0.60,
                "latency_reduction": 0.50,
                "accuracy_gain": 0.02,
            },
        }
        
        opt = optimizations.get(strategy, {})
        
        # Apply optimization
        optimized_metrics = ModelMetrics(
            accuracy=base_metrics.accuracy - opt.get("accuracy_loss", 0) + opt.get("accuracy_gain", 0),
            precision=base_metrics.precision * 0.98,
            recall=base_metrics.recall * 0.98,
            f1_score=base_metrics.f1_score * 0.98,
            latency_ms=base_metrics.latency_ms * opt.get("latency_reduction", 1.0),
            memory_mb=base_metrics.memory_mb * opt.get("size_reduction", 1.0),
            size_mb=base_metrics.size_mb * opt.get("size_reduction", 1.0),
        )
        
        self._optimization_history.append({
            "model": model_name,
            "strategy": strategy.value,
            "before": base_metrics,
            "after": optimized_metrics,
        })
        
        logger.info(f"Optimization complete: {optimized_metrics.size_mb:.1f}MB, {optimized_metrics.latency_ms:.1f}ms")
        
        return optimized_metrics

    def register_model(self, name: str, model_config: Dict) -> str:
        """Register a model in the registry."""
        model_id = hashlib.sha256(f"{name}_{len(self._model_registry)}".encode()).hexdigest()[:12]
        
        self._model_registry[model_id] = {
            "name": name,
            "config": model_config,
            "version": 1,
            "created_at": __import__('time').time(),
            "metrics": None,
            "optimized": False,
        }
        
        logger.info(f"Model registered: {name} -> {model_id}")
        return model_id

    def automl_search(self, task: str, time_budget_min: int = 30) -> Dict[str, Any]:
        """Run AutoML search for best model architecture."""
        logger.info(f"Starting AutoML search for {task} ({time_budget_min}min budget)")
        
        # Simulated AutoML trial results
        trials = [
            {"architecture": "transformer_small", "accuracy": 0.88, "latency_ms": 30},
            {"architecture": "transformer_base", "accuracy": 0.92, "latency_ms": 50},
            {"architecture": "transformer_large", "accuracy": 0.94, "latency_ms": 120},
            {"architecture": "lstm", "accuracy": 0.85, "latency_ms": 25},
            {"architecture": "gru", "accuracy": 0.86, "latency_ms": 28},
            {"architecture": "tcn", "accuracy": 0.89, "latency_ms": 35},
        ]
        
        # Find Pareto-optimal models
        best_accuracy = max(t["accuracy"] for t in trials)
        best_latency = min(t["latency_ms"] for t in trials)
        
        # Score by accuracy/latency tradeoff
        for trial in trials:
            trial["score"] = (trial["accuracy"] / best_accuracy) * 0.7 + (best_latency / trial["latency_ms"]) * 0.3
        
        best_trial = max(trials, key=lambda t: t["score"])
        
        self._automl_trials[task] = {
            "trials_run": len(trials),
            "best_architecture": best_trial["architecture"],
            "best_accuracy": best_trial["accuracy"],
            "best_latency_ms": best_trial["latency_ms"],
            "all_trials": trials,
        }
        
        logger.info(f"AutoML complete: {best_trial['architecture']} (acc={best_trial['accuracy']}, lat={best_trial['latency_ms']}ms)")
        
        return self._automl_trials[task]

    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """Get model information from registry."""
        return self._model_registry.get(model_id)

    def list_models(self) -> List[Dict]:
        """List all registered models."""
        return [
            {"id": mid, "name": m["name"], "version": m["version"], "optimized": m["optimized"]}
            for mid, m in self._model_registry.items()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get advanced ML statistics."""
        return {
            "models_registered": len(self._model_registry),
            "federated_configured": self._federated_config is not None,
            "optimizations_run": len(self._optimization_history),
            "automl_tasks": len(self._automl_trials),
        }


# Global default advanced ML engine
default_advanced_ml: Optional[AdvancedMLEngine] = None


def init_advanced_ml() -> AdvancedMLEngine:
    """Initialize global advanced ML engine."""
    global default_advanced_ml
    default_advanced_ml = AdvancedMLEngine()
    return default_advanced_ml
