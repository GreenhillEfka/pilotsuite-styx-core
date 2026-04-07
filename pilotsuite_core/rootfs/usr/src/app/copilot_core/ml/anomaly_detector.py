"""
Isolation Forest Anomaly Detector for Sensor Data

Implements ML-based anomaly detection using Isolation Forest algorithm.
Detects sudden energy spikes, unexpected activities, and anomalous sensor patterns.

Features:
- Isolation Forest for unsupervised anomaly detection
- Incremental learning (partial_fit for streaming updates)
- Anomaly scoring per sensor/group
- Configurable contamination rate
- Integration with alert system for critical anomalies
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import numpy as np
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
except ImportError:
    IsolationForest = None  # type: ignore[assignment,misc]
    StandardScaler = None  # type: ignore[assignment,misc]
import json
import os

from .feature_extractor import FeatureExtractor, ExtractedFeatures, FeatureConfig

logger = logging.getLogger(__name__)


class AnomalyLevel(Enum):
    """Anomaly severity levels."""
    NORMAL = "normal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyResult:
    """Result of anomaly detection for a single observation."""
    
    # Anomaly score (-1 to 1, where -1 is most anomalous)
    score: float
    
    # Binary prediction (1 = anomaly, 0 = normal)
    is_anomaly: bool
    
    # Anomaly level classification
    level: AnomalyLevel
    
    # Sensor/entity ID
    sensor_id: str
    
    # Timestamp of detection
    timestamp: datetime
    
    # Feature vector that was analyzed
    features: Dict[str, float]
    
    # Contributing features (features that contributed most to anomaly)
    contributing_features: List[str] = field(default_factory=list)
    
    # Raw sensor values (for context)
    raw_values: Optional[np.ndarray] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "score": self.score,
            "is_anomaly": self.is_anomaly,
            "level": self.level.value,
            "sensor_id": self.sensor_id,
            "timestamp": self.timestamp.isoformat(),
            "features": self.features,
            "contributing_features": self.contributing_features,
            "raw_values": self.raw_values.tolist() if self.raw_values is not None else None,
        }


@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection."""
    
    # Isolation Forest parameters
    n_estimators: int = 100
    max_samples: Union[int, float] = "auto"
    contamination: float = 0.05  # Expected proportion of anomalies
    max_features: float = 1.0
    bootstrap: bool = False
    
    # Anomaly thresholds
    low_threshold: float = -0.3  # Score below this = low anomaly
    medium_threshold: float = -0.5  # Score below this = medium anomaly
    high_threshold: float = -0.7  # Score below this = high anomaly
    critical_threshold: float = -0.9  # Score below this = critical anomaly
    
    # Learning parameters
    warm_start: bool = True  # Enable incremental learning
    random_state: int = 42
    
    # Minimum samples before detection can start
    min_samples_initial: int = 50
    min_samples_update: int = 10
    
    # Feature extraction
    feature_config: Optional[FeatureConfig] = None


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector for sensor data.
    
    Supports:
    - Batch anomaly detection
    - Incremental learning (partial_fit)
    - Per-sensor and grouped detection
    - Alert integration for critical anomalies
    """
    
    def __init__(
        self,
        config: Optional[AnomalyConfig] = None,
        model_dir: Optional[str] = None
    ):
        self.config = config or AnomalyConfig()
        self.model_dir = model_dir
        
        # Initialize feature extractor
        self.feature_extractor = FeatureExtractor(
            self.config.feature_config or FeatureConfig()
        )
        
        # Model and scaler
        self._model: Optional[IsolationForest] = None
        self._scaler: Optional[StandardScaler] = None
        
        # Training state
        self._is_fitted = False
        self._n_samples = 0
        self._feature_names: Optional[List[str]] = None
        
        # Per-sensor statistics
        self._sensor_stats: Dict[str, Dict[str, float]] = {}
        
        # Anomaly history (for trend analysis)
        self._anomaly_history: List[AnomalyResult] = []
        self._max_history = 1000
        
    def fit(self, training_data: Union[np.ndarray, Dict[str, np.ndarray]]) -> "AnomalyDetector":
        """
        Fit the anomaly detector on training data.
        
        Args:
            training_data: Either:
                - 2D numpy array (samples x features)
                - Dictionary mapping sensor IDs to value arrays
                
        Returns:
            Self for method chaining
        """
        logger.info("Fitting anomaly detector...")
        
        # Extract features from training data
        if isinstance(training_data, dict):
            # Multi-sensor data
            feature_vectors = []
            for sensor_id, values in training_data.items():
                try:
                    features = self.feature_extractor.extract(values)
                    feature_vectors.append(features.to_dict())
                    self._update_sensor_stats(sensor_id, values)
                except ValueError as e:
                    logger.warning(f"Skipping sensor {sensor_id}: {e}")
        else:
            # Single array - extract rolling window features
            feature_list = self.feature_extractor.extract_rolling(training_data)
            feature_vectors = [f.to_dict() for f in feature_list]
        
        if not feature_vectors:
            raise ValueError("No valid features extracted from training data")
        
        # Convert to array
        X = np.array([list(fv.values()) for fv in feature_vectors])
        self._feature_names = list(feature_vectors[0].keys())
        
        # Fit scaler
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)
        
        # Fit Isolation Forest
        self._model = IsolationForest(
            n_estimators=self.config.n_estimators,
            max_samples=self.config.max_samples,
            contamination=self.config.contamination,
            max_features=self.config.max_features,
            bootstrap=self.config.bootstrap,
            warm_start=self.config.warm_start,
            random_state=self.config.random_state,
        )
        self._model.fit(X_scaled)
        
        self._is_fitted = True
        self._n_samples = len(X)
        
        logger.info(f"Anomaly detector fitted with {self._n_samples} samples")
        return self
    
    def partial_fit(self, new_data: Union[np.ndarray, Dict[str, np.ndarray]]) -> "AnomalyDetector":
        """
        Incrementally update the model with new data.
        
        Uses warm_start to add new trees without full retraining.
        
        Args:
            new_data: New sensor data (same format as fit)
            
        Returns:
            Self for method chaining
        """
        if not self._is_fitted:
            logger.warning("Model not fitted yet. Calling fit() first.")
            return self.fit(new_data)
        
        # Extract features
        if isinstance(new_data, dict):
            feature_vectors = []
            for sensor_id, values in new_data.items():
                try:
                    features = self.feature_extractor.extract(values)
                    feature_vectors.append(features.to_dict())
                    self._update_sensor_stats(sensor_id, values)
                except ValueError:
                    continue
        else:
            feature_list = self.feature_extractor.extract_rolling(new_data)
            feature_vectors = [f.to_dict() for f in feature_list]
        
        if not feature_vectors:
            return self
        
        X = np.array([list(fv.values()) for fv in feature_vectors])
        
        # Scale new data
        X_scaled = self._scaler.transform(X)
        
        # Incrementally update model by adding more estimators
        n_new_estimators = max(1, len(X) // 10)  # Add 1 tree per 10 samples
        self._model.n_estimators += n_new_estimators
        self._model.fit(X_scaled)
        
        self._n_samples += len(X)
        
        logger.debug(f"Model updated with {len(X)} new samples, total: {self._n_samples}")
        return self
    
    def detect(
        self,
        data: Union[np.ndarray, Dict[str, np.ndarray]],
        sensor_id: Optional[str] = None
    ) -> Union[AnomalyResult, List[AnomalyResult]]:
        """
        Detect anomalies in new data.
        
        Args:
            data: Sensor data (array or dict of sensor_id -> values)
            sensor_id: Optional sensor ID for single-array input
            
        Returns:
            Single AnomalyResult or list of results
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        
        if self._n_samples < self.config.min_samples_initial:
            logger.warning(
                f"Insufficient training samples: {self._n_samples} < {self.config.min_samples_initial}"
            )
        
        # Handle single sensor case
        if isinstance(data, np.ndarray):
            if sensor_id is None:
                sensor_id = "unknown"
            return self._detect_single(data, sensor_id)
        
        # Multi-sensor case
        results = []
        for sid, values in data.items():
            try:
                result = self._detect_single(values, sid)
                results.append(result)
            except ValueError as e:
                logger.warning(f"Failed to detect anomalies for sensor {sid}: {e}")
        
        return results
    
    def _detect_single(self, values: np.ndarray, sensor_id: str) -> AnomalyResult:
        """Detect anomalies in a single sensor's data."""
        # Extract features
        features_obj = self.feature_extractor.extract(values)
        feature_dict = features_obj.to_dict()
        
        # Scale features
        X = np.array([list(feature_dict.values())])
        X_scaled = self._scaler.transform(X)
        
        # Get anomaly score and prediction
        score = float(self._model.score_samples(X_scaled)[0])
        prediction = int(self._model.predict(X_scaled)[0])
        
        # Determine anomaly level
        level = self._classify_anomaly_level(score)
        is_anomaly = prediction == -1
        
        # Find contributing features
        contributing = self._find_contributing_features(feature_dict, sensor_id)
        
        # Create result
        result = AnomalyResult(
            score=score,
            is_anomaly=is_anomaly,
            level=level,
            sensor_id=sensor_id,
            timestamp=datetime.now(timezone.utc),
            features=feature_dict,
            contributing_features=contributing,
            raw_values=values.copy(),
        )
        
        # Update history
        self._anomaly_history.append(result)
        if len(self._anomaly_history) > self._max_history:
            self._anomaly_history = self._anomaly_history[-self._max_history:]
        
        return result
    
    def _classify_anomaly_level(self, score: float) -> AnomalyLevel:
        """Classify anomaly level based on score."""
        if score >= self.config.low_threshold:
            return AnomalyLevel.NORMAL
        elif score >= self.config.medium_threshold:
            return AnomalyLevel.LOW
        elif score >= self.config.high_threshold:
            return AnomalyLevel.MEDIUM
        elif score >= self.config.critical_threshold:
            return AnomalyLevel.HIGH
        else:
            return AnomalyLevel.CRITICAL
    
    def _find_contributing_features(
        self,
        feature_dict: Dict[str, float],
        sensor_id: str
    ) -> List[str]:
        """
        Identify features that contributed most to the anomaly.
        
        Compares current features against historical sensor statistics.
        """
        if sensor_id not in self._sensor_stats:
            return list(feature_dict.keys())[:5]  # Return first 5 features
        
        stats = self._sensor_stats[sensor_id]
        deviations = []
        
        for feature, value in feature_dict.items():
            mean = stats.get(f"{feature}_mean", value)
            std = stats.get(f"{feature}_std", 1.0)
            
            if std < 1e-10:
                std = 1.0
            
            # Z-score deviation
            z_score = abs(value - mean) / std
            deviations.append((feature, z_score))
        
        # Sort by deviation and return top contributors
        deviations.sort(key=lambda x: x[1], reverse=True)
        return [feature for feature, _ in deviations[:5]]
    
    def _update_sensor_stats(self, sensor_id: str, values: np.ndarray) -> None:
        """Update running statistics for a sensor."""
        features = self.feature_extractor.extract(values)
        feature_dict = features.to_dict()
        
        if sensor_id not in self._sensor_stats:
            # Initialize stats
            self._sensor_stats[sensor_id] = {}
            for key, value in feature_dict.items():
                self._sensor_stats[sensor_id][f"{key}_mean"] = value
                self._sensor_stats[sensor_id][f"{key}_std"] = 0.0
                self._sensor_stats[sensor_id][f"{key}_min"] = value
                self._sensor_stats[sensor_id][f"{key}_max"] = value
                self._sensor_stats[sensor_id][f"{key}_count"] = 1
        else:
            # Update running statistics
            stats = self._sensor_stats[sensor_id]
            for key, value in feature_dict.items():
                count = stats.get(f"{key}_count", 0) + 1
                old_mean = stats.get(f"{key}_mean", value)
                
                # Welford's online algorithm for mean and variance
                new_mean = old_mean + (value - old_mean) / count
                old_m2 = stats.get(f"{key}_m2", 0.0)
                new_m2 = old_m2 + (value - old_mean) * (value - new_mean)
                
                stats[f"{key}_mean"] = new_mean
                stats[f"{key}_m2"] = new_m2
                stats[f"{key}_count"] = count
                stats[f"{key}_std"] = np.sqrt(new_m2 / count) if count > 1 else 0.0
                stats[f"{key}_min"] = min(stats.get(f"{key}_min", value), value)
                stats[f"{key}_max"] = max(stats.get(f"{key}_max", value), value)
    
    def get_anomaly_history(
        self,
        sensor_id: Optional[str] = None,
        level: Optional[AnomalyLevel] = None,
        limit: int = 100
    ) -> List[AnomalyResult]:
        """
        Retrieve anomaly detection history.
        
        Args:
            sensor_id: Filter by sensor ID
            level: Filter by minimum anomaly level
            limit: Maximum number of results to return
            
        Returns:
            List of AnomalyResult objects
        """
        results = self._anomaly_history.copy()
        
        if sensor_id:
            results = [r for r in results if r.sensor_id == sensor_id]
        
        if level:
            level_order = [AnomalyLevel.NORMAL, AnomalyLevel.LOW, AnomalyLevel.MEDIUM,
                          AnomalyLevel.HIGH, AnomalyLevel.CRITICAL]
            min_index = level_order.index(level)
            results = [r for r in results if level_order.index(r.level) >= min_index]
        
        return results[-limit:]
    
    def get_sensor_health(self, sensor_id: str) -> Dict[str, Any]:
        """
        Get health summary for a specific sensor.
        
        Returns:
            Dictionary with sensor health metrics
        """
        if sensor_id not in self._sensor_stats:
            return {"status": "unknown", "message": "No data for sensor"}
        
        # Get recent anomalies for this sensor
        recent_anomalies = [
            r for r in self._anomaly_history[-100:]
            if r.sensor_id == sensor_id and r.is_anomaly
        ]
        
        anomaly_rate = len(recent_anomalies) / max(1, len(self._anomaly_history[-100:]))
        
        # Determine health status
        if anomaly_rate > 0.3:
            status = "critical"
        elif anomaly_rate > 0.1:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "sensor_id": sensor_id,
            "status": status,
            "anomaly_rate": round(anomaly_rate, 4),
            "recent_anomalies": len(recent_anomalies),
            "total_samples": self._n_samples,
            "stats": self._sensor_stats[sensor_id],
        }
    
    def save_model(self, path: Optional[str] = None) -> str:
        """
        Save model and statistics to disk.
        
        Args:
            path: Optional path to save model (uses model_dir if not specified)
            
        Returns:
            Path where model was saved
        """
        if path is None:
            if self.model_dir is None:
                raise ValueError("No model directory configured")
            path = os.path.join(self.model_dir, "anomaly_model.json")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Serialize model state
        model_state = {
            "config": {
                "n_estimators": self.config.n_estimators,
                "contamination": self.config.contamination,
                "max_samples": self.config.max_samples,
                "max_features": self.config.max_features,
                "bootstrap": self.config.bootstrap,
                "warm_start": self.config.warm_start,
                "random_state": self.config.random_state,
            },
            "is_fitted": self._is_fitted,
            "n_samples": self._n_samples,
            "feature_names": self._feature_names,
            "sensor_stats": self._sensor_stats,
        }
        
        # Save scaler parameters
        if self._scaler is not None:
            model_state["scaler"] = {
                "mean": self._scaler.mean_.tolist(),
                "scale": self._scaler.scale_.tolist(),
                "var": self._scaler.var_.tolist(),
            }
        
        # Save model parameters (IsolationForest doesn't serialize easily)
        if self._model is not None:
            model_state["model"] = {
                "estimators": len(self._model.estimators_),
                "n_estimators": self._model.n_estimators,
            }
        
        with open(path, "w") as f:
            json.dump(model_state, f, indent=2)
        
        logger.info(f"Model saved to {path}")
        return path
    
    def load_model(self, path: Optional[str] = None) -> "AnomalyDetector":
        """
        Load model from disk.
        
        Args:
            path: Optional path to load model (uses model_dir if not specified)
            
        Returns:
            Self for method chaining
        """
        if path is None:
            if self.model_dir is None:
                raise ValueError("No model directory configured")
            path = os.path.join(self.model_dir, "anomaly_model.json")
        
        with open(path, "r") as f:
            model_state = json.load(f)
        
        # Restore config
        self.config.n_estimators = model_state["config"]["n_estimators"]
        self.config.contamination = model_state["config"]["contamination"]
        self.config.max_samples = model_state["config"]["max_samples"]
        self.config.max_features = model_state["config"]["max_features"]
        self.config.bootstrap = model_state["config"]["bootstrap"]
        self.config.warm_start = model_state["config"]["warm_start"]
        self.config.random_state = model_state["config"]["random_state"]
        
        # Restore state
        self._is_fitted = model_state["is_fitted"]
        self._n_samples = model_state["n_samples"]
        self._feature_names = model_state["feature_names"]
        self._sensor_stats = model_state["sensor_stats"]
        
        # Restore scaler
        if "scaler" in model_state:
            self._scaler = StandardScaler()
            self._scaler.mean_ = np.array(model_state["scaler"]["mean"])
            self._scaler.scale_ = np.array(model_state["scaler"]["scale"])
            self._scaler.var_ = np.array(model_state["scaler"]["var"])
        
        # Reinitialize model (will need refit or partial_fit)
        if self._is_fitted:
            self._model = IsolationForest(
                n_estimators=self.config.n_estimators,
                max_samples=self.config.max_samples,
                contamination=self.config.contamination,
                max_features=self.config.max_features,
                bootstrap=self.config.bootstrap,
                warm_start=self.config.warm_start,
                random_state=self.config.random_state,
            )
            logger.info(f"Model loaded from {path}, but needs refit/partial_fit")
        
        logger.info(f"Model loaded from {path}")
        return self


class ContextAwareAnomalyDetector:
    """Extended anomaly detector with temporal + device relationship context.

    Wraps the main AnomalyDetector with additional context analysis:
    - Temporal patterns (hour-of-day, day-of-week expectations)
    - Device relationship scoring (correlated device groups)
    - Adaptive thresholding based on recent anomaly rates

    Migrated from pilotsuite-styx-ha ml/patterns/anomaly_detector.py.
    """

    def __init__(
        self,
        detector: Optional[AnomalyDetector] = None,
        temporal_window_hours: int = 24,
        device_relationships: Optional[Dict[str, List[str]]] = None,
        adaptive_threshold: bool = True,
    ):
        self.detector = detector or AnomalyDetector()
        self.temporal_window_hours = temporal_window_hours
        self.device_relationships = device_relationships or {}
        self.adaptive_threshold = adaptive_threshold
        self.temporal_patterns: Dict[str, List[float]] = {}
        self._recent_scores: List[float] = []

    def update_with_context(
        self,
        device_id: str,
        values: np.ndarray,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Detect anomaly with temporal + device-relationship context.

        Returns enriched result dict with base_result, temporal_context,
        relationship_context, and adaptive_threshold info.
        """
        # Run base detection
        base_result = self.detector.detect(values, sensor_id=device_id)
        if isinstance(base_result, list):
            base_result = base_result[0] if base_result else None
        if base_result is None:
            return {"status": "error", "message": "Detection failed"}

        # Temporal analysis
        temporal_info = self._analyze_temporal(device_id, context or {})

        # Relationship analysis
        relationship_info = self._analyze_relationships(device_id)

        # Adaptive threshold adjustment
        self._recent_scores.append(base_result.score)
        self._recent_scores = self._recent_scores[-50:]
        adj_threshold = self._get_adaptive_threshold() if self.adaptive_threshold else None

        return {
            "score": base_result.score,
            "is_anomaly": base_result.is_anomaly,
            "level": base_result.level.value,
            "sensor_id": device_id,
            "temporal_context": temporal_info,
            "relationship_context": relationship_info,
            "adaptive_threshold": adj_threshold,
        }

    def _analyze_temporal(self, device_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        hour = context.get("hour_of_day", 12)
        dow = context.get("day_of_week", 0)
        key = f"{device_id}_{hour}_{dow}"
        return {
            "hour_of_day": hour,
            "day_of_week": dow,
            "expected_pattern": key in self.temporal_patterns,
            "history_len": len(self.temporal_patterns.get(key, [])),
        }

    def _analyze_relationships(self, device_id: str) -> Dict[str, Any]:
        related = self.device_relationships.get(device_id, [])
        return {
            "related_devices": related,
            "group_size": len(related),
        }

    def _get_adaptive_threshold(self) -> float:
        if len(self._recent_scores) < 10:
            return -0.5
        mean_score = float(np.mean(self._recent_scores))
        if mean_score < -0.6:
            return -0.4  # More sensitive when many anomalies
        if mean_score > -0.2:
            return -0.6  # Less sensitive when few anomalies
        return -0.5


def create_anomaly_detector(
    n_estimators: int = 100,
    contamination: float = 0.05,
    model_dir: Optional[str] = None
) -> AnomalyDetector:
    """
    Factory function to create a configured AnomalyDetector.
    
    Args:
        n_estimators: Number of trees in the forest
        contamination: Expected proportion of anomalies
        model_dir: Directory for model persistence
        
    Returns:
        Configured AnomalyDetector instance
    """
    config = AnomalyConfig(
        n_estimators=n_estimators,
        contamination=contamination,
    )
    return AnomalyDetector(config, model_dir)
