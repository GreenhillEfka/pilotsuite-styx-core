"""ML Inference Engine — Real-time pattern inference for smart home.

Features:
- Low-latency predictions with caching
- Batch processing
- Streaming window analysis
- Confidence scoring + alert generation
- Model integrity verification (SHA256)

Migrated from pilotsuite-styx-ha (pure logic, no HA dependencies).
"""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = "/data/ml/models"


class InferenceEngine:
    """Real-time inference engine for ML models."""

    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        cache_ttl_seconds: float = 300.0,
        batch_size: int = 10,
        enabled: bool = True,
    ):
        self.model_path = Path(model_path)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.batch_size = batch_size
        self.enabled = enabled

        self.models: Dict[str, Any] = {}
        self.model_configs: Dict[str, Dict] = {}

        self.cache: Dict[str, Dict] = {}
        self.cache_lock = threading.Lock()

        self.inference_count = 0
        self.inference_time_total = 0.0
        self.alerts: List[Dict] = []
        self._is_initialized = False

    def load_model(self, model_name: str) -> bool:
        """Load a model from disk with integrity verification."""
        try:
            path = self.model_path / f"{model_name}_model.pkl"
            hash_path = self.model_path / f"{model_name}_model.pkl.sha256"

            if not path.exists():
                return False

            # Verify hash before loading (security)
            if hash_path.exists():
                with open(path, "rb") as f:
                    current_hash = hashlib.sha256(f.read()).hexdigest()
                with open(hash_path, "r") as f:
                    expected_hash = f.read().strip()
                if current_hash != expected_hash:
                    _LOGGER.warning("Security: Model %s hash mismatch!", model_name)
                    return False

            with open(path, "rb") as f:
                self.models[model_name] = pickle.load(f)  # noqa: S301

            meta_path = self.model_path / f"{model_name}_metadata.json"
            if meta_path.exists():
                with open(meta_path, "r") as f:
                    self.model_configs[model_name] = json.load(f)

            return True

        except Exception as e:
            _LOGGER.error("Failed to load model %s: %s", model_name, e)
            return False

    def predict(
        self,
        model_name: str,
        features: Dict[str, Any],
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Run inference on features."""
        if not self.enabled:
            return {"status": "disabled"}

        if model_name not in self.models:
            return {"status": "error", "message": f"Model {model_name} not loaded"}

        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key(model_name, features)
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached

        feature_names = self._get_feature_names(model_name)
        if feature_names is None:
            return {"status": "error", "message": "Feature names not configured"}

        X = self._prepare_features(features, feature_names)
        if X is None:
            return {"status": "error", "message": "Invalid features"}

        start_time = time.time()
        try:
            result = self._run_inference(model_name, X)
            self.inference_count += 1
            self.inference_time_total += time.time() - start_time

            if use_cache and cache_key:
                self._put_in_cache(cache_key, result)

            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def batch_predict(
        self,
        model_name: str,
        feature_batches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Run batch inference."""
        if not self.enabled:
            return [{"status": "disabled"}] * len(feature_batches)
        return [self.predict(model_name, f, use_cache=False) for f in feature_batches]

    def generate_alerts(
        self,
        model_name: str,
        prediction: Dict[str, Any],
        threshold: float = 0.9,
    ) -> Optional[Dict]:
        """Generate alert if prediction confidence exceeds threshold."""
        if not self.enabled or prediction.get("status") != "success":
            return None

        confidence = prediction.get("confidence", 0.0)
        if confidence >= threshold:
            alert = {
                "type": "high_confidence_anomaly",
                "model_name": model_name,
                "timestamp": time.time(),
                "prediction": prediction,
                "confidence": confidence,
                "threshold": threshold,
            }
            self.alerts.append(alert)
            self.alerts = self.alerts[-100:]
            return alert
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get inference engine statistics."""
        avg_time = (
            self.inference_time_total / self.inference_count
            if self.inference_count > 0 else 0.0
        )
        return {
            "total_inferences": self.inference_count,
            "average_time_ms": avg_time * 1000,
            "cache_size": len(self.cache),
            "alerts_count": len(self.alerts),
            "models_loaded": len(self.models),
            "recent_alerts": self.alerts[-10:],
        }

    def clear_cache(self) -> None:
        with self.cache_lock:
            self.cache.clear()

    def reset(self) -> None:
        self.models.clear()
        self.model_configs.clear()
        self.clear_cache()
        self.inference_count = 0
        self.inference_time_total = 0.0
        self.alerts.clear()
        self._is_initialized = False

    # ── Internal helpers ─────────────────────────────────────────────

    def _generate_cache_key(self, model_name: str, features: Dict[str, Any]) -> str:
        sorted_features = sorted(features.items())
        return f"{model_name}:{sorted_features}"

    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        with self.cache_lock:
            cached = self.cache.get(cache_key)
            if cached is None:
                return None
            if time.time() - cached["timestamp"] > self.cache_ttl_seconds:
                del self.cache[cache_key]
                return None
            return cached["result"]

    def _put_in_cache(self, cache_key: str, result: Dict) -> None:
        with self.cache_lock:
            self.cache[cache_key] = {"timestamp": time.time(), "result": result}

    def _get_feature_names(self, model_name: str) -> Optional[List[str]]:
        config = self.model_configs.get(model_name, {})
        return config.get("feature_names")

    def _prepare_features(self, features: Dict[str, Any], feature_names: List[str]) -> Optional[Any]:
        try:
            return [[float(features.get(name)) for name in feature_names]]
        except (ValueError, TypeError):
            return None

    def _run_inference(self, model_name: str, X: Any) -> Dict[str, Any]:
        model = self.models[model_name]
        prediction = model.predict(X)[0] if hasattr(model, "predict") else 0
        confidence = 0.0
        if hasattr(model, "decision_function"):
            try:
                confidence = float(model.decision_function(X)[0])
            except Exception:
                pass
        return {
            "status": "success",
            "prediction": prediction,
            "confidence": confidence,
            "model_name": model_name,
            "timestamp": time.time(),
        }


class StreamingInferenceEngine(InferenceEngine):
    """Extended inference engine with streaming window support."""

    def __init__(self, window_size: int = 10, window_stride: int = 1, **kwargs):
        super().__init__(**kwargs)
        self.window_size = window_size
        self.window_stride = window_stride
        self.windows: Dict[str, List[Dict]] = {}

    def update_stream(
        self,
        model_name: str,
        feature: Dict[str, Any],
        stream_id: str = "default",
    ) -> Dict[str, Any]:
        """Update streaming window and run inference when window is full."""
        if model_name not in self.models:
            return {"status": "error", "message": "Model not loaded"}

        if stream_id not in self.windows:
            self.windows[stream_id] = []

        self.windows[stream_id].append({"feature": feature, "timestamp": time.time()})

        if len(self.windows[stream_id]) >= self.window_size:
            features_batch = [w["feature"] for w in self.windows[stream_id]]
            results = self.batch_predict(model_name, features_batch)
            self.windows[stream_id] = self.windows[stream_id][-self.window_size:]
            return {
                "status": "success",
                "stream_id": stream_id,
                "window_size": len(features_batch),
                "results": results,
                "timestamp": time.time(),
            }

        return {"status": "waiting", "window_size": len(self.windows[stream_id])}

    def get_stream_statistics(self, stream_id: str) -> Dict[str, Any]:
        if stream_id not in self.windows:
            return {"status": "unknown"}
        window = self.windows[stream_id]
        return {
            "stream_id": stream_id,
            "window_size": len(window),
            "current_values": window[-1]["feature"] if window else None,
        }

    def reset_stream(self, stream_id: str) -> None:
        self.windows.pop(stream_id, None)

    def reset(self) -> None:
        super().reset()
        self.windows.clear()
