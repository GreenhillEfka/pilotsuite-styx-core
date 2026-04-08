"""ML Training Pipeline — On-device training for pattern models.

Features:
- Model registration with hyperparameters
- Training data management (bounded storage)
- Model persistence (pickle + metadata)
- Incremental learning (partial_fit)
- Training history + metrics

Migrated from pilotsuite-styx-ha (pure logic, no HA dependencies).
"""
from __future__ import annotations

import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

_LOGGER = logging.getLogger(__name__)

_DEFAULT_STORAGE_PATH = "/data/ml/training"


class TrainingPipeline:
    """On-device training pipeline for ML models."""

    def __init__(
        self,
        storage_path: str = _DEFAULT_STORAGE_PATH,
        max_training_data: int = 10000,
        auto_save: bool = True,
        enabled: bool = True,
    ):
        self.storage_path = Path(storage_path)
        self.max_training_data = max_training_data
        self.auto_save = auto_save
        self.enabled = enabled

        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.training_data: Dict[str, List[Dict]] = {}
        self.model_metrics: Dict[str, Dict] = {}
        self.training_history: List[Dict] = []
        self.models: Dict[str, Any] = {}
        self._model_classes: Dict[str, Any] = {}
        self._is_initialized = False

    def register_model(
        self,
        model_name: str,
        model_class: Any,
        feature_names: List[str],
        **hyperparams,
    ) -> None:
        """Register a model for training."""
        if not self.enabled:
            return
        self._model_classes[model_name] = {
            "class": model_class,
            "feature_names": feature_names,
            "hyperparams": hyperparams,
        }
        self.training_data[model_name] = []
        self.model_metrics[model_name] = {
            "samples": 0,
            "last_trained": None,
            "last_trained_epoch": 0,
        }

    def add_training_data(
        self,
        model_name: str,
        features: Dict[str, Any],
        target: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add training data for a model."""
        if not self.enabled or model_name not in self._model_classes:
            return False

        self.training_data[model_name].append({
            "features": features,
            "target": target,
            "context": context or {},
            "timestamp": time.time(),
        })

        # Bound storage
        if len(self.training_data[model_name]) > self.max_training_data:
            self.training_data[model_name] = self.training_data[model_name][-self.max_training_data:]

        self.model_metrics[model_name]["samples"] = len(self.training_data[model_name])

        if self.auto_save:
            self._save_training_data(model_name)
        return True

    def train_model(
        self,
        model_name: str,
        data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Train a model using stored or provided data."""
        if not self.enabled:
            return {"status": "disabled"}
        if model_name not in self._model_classes:
            return {"status": "error", "message": f"Model {model_name} not registered"}

        if data is None:
            data = self.training_data.get(model_name, [])
        if not data:
            return {"status": "error", "message": "No training data available"}

        feature_names = self._model_classes[model_name]["feature_names"]
        X, y = self._prepare_data(data, feature_names)
        if X is None:
            return {"status": "error", "message": "Failed to prepare training data"}

        model_class = self._model_classes[model_name]["class"]
        hyperparams = self._model_classes[model_name]["hyperparams"]
        model = model_class(**hyperparams)

        try:
            start = time.time()
            model.fit(X)
            train_time = time.time() - start

            self.models[model_name] = model
            self.model_metrics[model_name].update({
                "status": "trained",
                "last_trained": time.time(),
                "last_trained_epoch": self.model_metrics[model_name].get("last_trained_epoch", 0) + 1,
                "training_samples": len(data),
                "training_time_seconds": round(train_time, 3),
            })

            if self.auto_save:
                self._save_model(model_name)

            self.training_history.append({
                "model_name": model_name,
                "samples": len(data),
                "timestamp": time.time(),
                "status": "success",
                "duration_s": round(train_time, 3),
            })

            return {
                "status": "success",
                "model_name": model_name,
                "samples": len(data),
                "metrics": self.model_metrics[model_name],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def load_model(self, model_name: str) -> Optional[Any]:
        """Load a trained model from disk."""
        try:
            path = self.storage_path / f"{model_name}_model.pkl"
            if not path.exists():
                return None
            with open(path, "rb") as f:
                model = pickle.load(f)  # noqa: S301
            self.models[model_name] = model
            return model
        except Exception as e:
            _LOGGER.error("Failed to load model %s: %s", model_name, e)
            return None

    def get_training_status(self) -> Dict[str, Any]:
        """Get overall training status."""
        return {
            "models_registered": len(self._model_classes),
            "models_trained": sum(1 for m in self.model_metrics.values() if m.get("status") == "trained"),
            "total_training_samples": sum(m.get("samples", 0) for m in self.model_metrics.values()),
            "training_history": self.training_history[-10:],
        }

    def reset(self) -> None:
        self.training_data.clear()
        self.model_metrics.clear()
        self.models.clear()
        self.training_history.clear()
        self._is_initialized = False

    # ── Internal helpers ─────────────────────────────────────────────

    def _prepare_data(self, data: List[Dict], feature_names: List[str]) -> tuple:
        X, y = [], []
        for point in data:
            features = []
            for name in feature_names:
                value = point["features"].get(name)
                if value is None:
                    break
                try:
                    features.append(float(value))
                except (ValueError, TypeError):
                    break
            else:
                X.append(features)
                if point.get("target") is not None:
                    y.append(point["target"])
        if not X:
            return None, None
        return np.array(X), np.array(y) if y else None

    def _save_training_data(self, model_name: str) -> None:
        try:
            path = self.storage_path / f"{model_name}_training_data.pkl"
            with open(path, "wb") as f:
                pickle.dump(self.training_data[model_name], f)
        except Exception as e:
            _LOGGER.error("Failed to save training data for %s: %s", model_name, e)

    def _save_model(self, model_name: str) -> None:
        if model_name not in self.models:
            return
        try:
            path = self.storage_path / f"{model_name}_model.pkl"
            with open(path, "wb") as f:
                pickle.dump(self.models[model_name], f)
            meta_path = self.storage_path / f"{model_name}_metadata.json"
            with open(meta_path, "w") as f:
                json.dump({
                    "model_name": model_name,
                    "saved_at": time.time(),
                    "metrics": self.model_metrics[model_name],
                    "feature_names": self._model_classes.get(model_name, {}).get("feature_names", []),
                }, f)
        except Exception as e:
            _LOGGER.error("Failed to save model %s: %s", model_name, e)


class IncrementalTrainingPipeline(TrainingPipeline):
    """Training pipeline with incremental learning (partial_fit) support."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._incremental_models: Dict[str, bool] = {}

    def register_incremental_model(
        self,
        model_name: str,
        model_class: Any,
        feature_names: List[str],
        **hyperparams,
    ) -> None:
        """Register a model with incremental learning support."""
        super().register_model(model_name, model_class, feature_names, **hyperparams)
        self._incremental_models[model_name] = True

    def incremental_update(
        self,
        model_name: str,
        features: Dict[str, Any],
        target: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Perform incremental update on a model."""
        if not self.enabled:
            return {"status": "disabled"}
        if model_name not in self._incremental_models:
            return {"status": "error", "message": "Model does not support incremental learning"}

        if not self.add_training_data(model_name, features, target):
            return {"status": "error", "message": "Failed to add training data"}

        model = self.models.get(model_name)
        if model is None:
            return {"status": "error", "message": "No existing model found"}

        try:
            feature_names = self._model_classes[model_name]["feature_names"]
            X = np.array([float(features.get(name)) for name in feature_names]).reshape(1, -1)

            if hasattr(model, "partial_fit"):
                y = [target] if target is not None else None
                model.partial_fit(X, y)
            else:
                recent_data = self.training_data[model_name][-100:]
                self._train_model_from_data(model_name, recent_data)

            return {
                "status": "success",
                "model_name": model_name,
                "samples_seen": len(self.training_data[model_name]),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _train_model_from_data(self, model_name: str, data: List[Dict]) -> None:
        feature_names = self._model_classes[model_name]["feature_names"]
        model_class = self._model_classes[model_name]["class"]
        hyperparams = self._model_classes[model_name]["hyperparams"]
        X, _ = self._prepare_data(data, feature_names)
        if X is None:
            return
        model = model_class(**hyperparams)
        model.fit(X)
        self.models[model_name] = model
