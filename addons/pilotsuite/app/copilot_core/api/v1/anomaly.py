"""
Anomaly Detection API Blueprint

Provides REST API endpoints for ML-based anomaly detection.

Endpoints:
- POST /api/v1/anomaly/detect - Detect anomalies in sensor data
- GET /api/v1/anomaly/history - Get anomaly detection history
- GET /api/v1/anomaly/sensor/:sensor_id/health - Get sensor health status
- POST /api/v1/anomaly/train - Train/update anomaly detection model
- GET /api/v1/anomaly/model/status - Get model status
- POST /api/v1/anomaly/model/save - Save model to disk
- POST /api/v1/anomaly/model/load - Load model from disk

Usage:
    from copilot_core.api.v1.anomaly import anomaly_bp
    app.register_blueprint(anomaly_bp)
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import numpy as np

from flask import Blueprint, jsonify, request

from copilot_core.ml.anomaly_detector import (
    AnomalyDetector,
    AnomalyConfig,
    AnomalyLevel,
    AnomalyResult,
    create_anomaly_detector,
)
from copilot_core.ml.feature_extractor import FeatureExtractor, FeatureConfig
from copilot_core.ml.model_store import ModelStore, ModelMetadata, TrainingRecord

logger = logging.getLogger(__name__)

# Create blueprint
anomaly_bp = Blueprint("anomaly", __name__)

# Global detector instance (initialized on first use, double-checked locking)
_detector: Optional[AnomalyDetector] = None
_detector_lock = threading.Lock()
_model_store: Optional[ModelStore] = None
_model_store_lock = threading.Lock()


def get_detector() -> AnomalyDetector:
    """Get or create the global anomaly detector instance (thread-safe)."""
    global _detector

    if _detector is None:
        with _detector_lock:
            if _detector is None:
                model_dir = os.environ.get("PILOTSUITE_MODEL_DIR", "/data/ml_models")
                _detector = create_anomaly_detector(
                    n_estimators=100,
                    contamination=0.05,
                    model_dir=model_dir,
                )
    return _detector


def get_model_store() -> ModelStore:
    """Get or create the global model store instance (thread-safe)."""
    global _model_store

    if _model_store is None:
        with _model_store_lock:
            if _model_store is None:
                store_path = os.environ.get("PILOTSUITE_MODEL_DIR", "/data/ml_models")
                _model_store = ModelStore(store_path)
    return _model_store


def _bad_request(message: str, error: str = "invalid_request"):
    """Return a consistent 400 JSON response."""
    return jsonify({"error": error, "message": message}), 400


def _get_json_object(*, required: bool = False) -> tuple[Optional[Dict[str, Any]], Optional[Any]]:
    """Safely parse a JSON object body without raising 415 for non-JSON input."""
    data = request.get_json(silent=True)
    raw_body = request.get_data(cache=True)

    if data is None:
        if raw_body:
            return None, _bad_request("Request body must be a valid JSON object")
        if required:
            return None, _bad_request("Request body must be JSON")
        return {}, None

    if not isinstance(data, dict):
        return None, _bad_request("Request body must be a JSON object")

    return data, None


def _parse_int_param(value: Any, field_name: str) -> tuple[Optional[int], Optional[Any]]:
    """Safely parse an integer request parameter."""
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, _bad_request(f"'{field_name}' must be an integer")


def _parse_float_param(value: Any, field_name: str) -> tuple[Optional[float], Optional[Any]]:
    """Safely parse a float request parameter."""
    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, _bad_request(f"'{field_name}' must be a number")


def _parse_numeric_array(values: Any, field_name: str) -> tuple[Optional[np.ndarray], Optional[Any]]:
    """Safely parse a numeric array from request data."""
    if isinstance(values, (str, bytes)) or values is None:
        return None, _bad_request(f"'{field_name}' must be an array of numbers")

    try:
        parsed = np.array(values, dtype=np.float64)
    except (TypeError, ValueError):
        return None, _bad_request(f"'{field_name}' must be an array of numbers")

    if parsed.size == 0:
        return None, _bad_request(f"'{field_name}' must not be empty")

    return parsed, None


@anomaly_bp.route("/anomaly/detect", methods=["POST"])
def detect_anomalies():
    """
    Detect anomalies in sensor data.
    
    Request body:
    {
        "sensor_id": "sensor_123",  # Optional for single sensor
        "values": [1.2, 1.5, 1.3, ...],  # Array of sensor readings
        # OR
        "sensors": {  # For multi-sensor detection
            "sensor_1": [1.2, 1.5, ...],
            "sensor_2": [2.1, 2.3, ...]
        }
    }
    
    Response:
    {
        "ok": true,
        "results": [
            {
                "sensor_id": "sensor_123",
                "score": -0.45,
                "is_anomaly": true,
                "level": "medium",
                "timestamp": "2024-03-01T12:00:00Z",
                "features": {...},
                "contributing_features": ["std", "roc_max", ...]
            }
        ]
    }
    """
    try:
        data, error_response = _get_json_object(required=True)
        if error_response:
            return error_response

        detector = get_detector()
        
        # Handle multi-sensor vs single-sensor input
        if "sensors" in data:
            if not isinstance(data["sensors"], dict) or not data["sensors"]:
                return _bad_request("'sensors' must be a non-empty object mapping sensor IDs to numeric arrays")

            # Multi-sensor detection
            sensor_data = {}
            for sensor_id, values in data["sensors"].items():
                parsed_values, error_response = _parse_numeric_array(values, f"sensors.{sensor_id}")
                if error_response:
                    return error_response
                sensor_data[sensor_id] = parsed_values
            
            results = detector.detect(sensor_data)
        
        elif "values" in data:
            # Single sensor detection
            sensor_id = data.get("sensor_id", "unknown")
            values, error_response = _parse_numeric_array(data["values"], "values")
            if error_response:
                return error_response
            
            result = detector.detect(values, sensor_id=sensor_id)
            results = [result] if isinstance(result, AnomalyResult) else result
        
        else:
            return jsonify({
                "error": "invalid_request",
                "message": "Request must include 'values' or 'sensors' field",
            }), 400
        
        # Convert results to dict format
        response_results = []
        critical_anomalies = []
        
        for result in results:
            result_dict = result.to_dict()
            response_results.append(result_dict)
            
            # Track critical anomalies for immediate alerting
            if result.level == AnomalyLevel.CRITICAL:
                critical_anomalies.append(result_dict)
        
        # Log critical anomalies
        if critical_anomalies:
            logger.warning(
                f"Detected {len(critical_anomalies)} critical anomalies: "
                f"{[a['sensor_id'] for a in critical_anomalies]}"
            )
        
        return jsonify({
            "ok": True,
            "results": response_results,
            "critical_count": len(critical_anomalies),
            "total_count": len(results),
        }), 200
        
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        return jsonify({
            "error": "detection_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/history", methods=["GET"])
def get_anomaly_history():
    """
    Get anomaly detection history.
    
    Query params:
    - sensor_id: Filter by sensor ID (optional)
    - level: Minimum anomaly level (normal, low, medium, high, critical)
    - limit: Maximum number of results (default: 100)
    
    Response:
    {
        "ok": true,
        "history": [...],
        "total": 150
    }
    """
    try:
        sensor_id = request.args.get("sensor_id")
        level_str = request.args.get("level")
        limit, error_response = _parse_int_param(request.args.get("limit", "100"), "limit")
        if error_response:
            return error_response

        detector = get_detector()
        
        # Parse level filter
        level = None
        if level_str:
            try:
                level = AnomalyLevel(level_str.lower())
            except ValueError:
                return jsonify({
                    "error": "invalid_level",
                    "message": f"Invalid level: {level_str}. Must be one of: normal, low, medium, high, critical",
                }), 400
        
        history = detector.get_anomaly_history(
            sensor_id=sensor_id,
            level=level,
            limit=limit,
        )
        
        return jsonify({
            "ok": True,
            "history": [h.to_dict() for h in history],
            "total": len(history),
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get anomaly history: {e}")
        return jsonify({
            "error": "history_fetch_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/sensor/<sensor_id>/health", methods=["GET"])
def get_sensor_health(sensor_id: str):
    """
    Get health status for a specific sensor.
    
    Response:
    {
        "ok": true,
        "health": {
            "sensor_id": "sensor_123",
            "status": "healthy",  # healthy, degraded, critical
            "anomaly_rate": 0.05,
            "recent_anomalies": 5,
            "total_samples": 1000,
            "stats": {...}
        }
    }
    """
    try:
        detector = get_detector()
        health = detector.get_sensor_health(sensor_id)
        
        return jsonify({
            "ok": True,
            "health": health,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get sensor health: {e}")
        return jsonify({
            "error": "health_fetch_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/train", methods=["POST"])
def train_model():
    """
    Train or update the anomaly detection model.
    
    Request body:
    {
        "data": {  # Training data
            "sensor_1": [1.2, 1.5, ...],
            "sensor_2": [2.1, 2.3, ...]
        },
        # OR
        "values": [1.2, 1.5, ...],  # Single sensor data
        
        "incremental": true,  # Use partial_fit instead of full fit
        "config": {  # Optional configuration overrides
            "n_estimators": 100,
            "contamination": 0.05
        }
    }
    
    Response:
    {
        "ok": true,
        "training_id": "train_abc123",
        "samples": 1000,
        "duration_seconds": 2.5,
        "model_status": "fitted"
    }
    """
    try:
        data, error_response = _get_json_object(required=True)
        if error_response:
            return error_response

        detector = get_detector()
        
        # Extract training data
        if "data" in data:
            if not isinstance(data["data"], dict) or not data["data"]:
                return _bad_request("'data' must be a non-empty object mapping sensor IDs to numeric arrays")

            training_data = {}
            for sensor_id, values in data["data"].items():
                parsed_values, error_response = _parse_numeric_array(values, f"data.{sensor_id}")
                if error_response:
                    return error_response
                training_data[sensor_id] = parsed_values
        elif "values" in data:
            training_data, error_response = _parse_numeric_array(data["values"], "values")
            if error_response:
                return error_response
        else:
            return _bad_request("Request must include 'data' or 'values' field")
        
        # Apply config overrides
        if "config" in data:
            config = data["config"]
            if not isinstance(config, dict):
                return _bad_request("'config' must be an object")
            if "n_estimators" in config:
                n_estimators, error_response = _parse_int_param(config["n_estimators"], "config.n_estimators")
                if error_response:
                    return error_response
                detector.config.n_estimators = n_estimators
            if "contamination" in config:
                contamination, error_response = _parse_float_param(config["contamination"], "config.contamination")
                if error_response:
                    return error_response
                detector.config.contamination = contamination
        
        # Train model
        start_time = datetime.now(timezone.utc)
        
        is_incremental = data.get("incremental", False)
        
        if is_incremental:
            detector.partial_fit(training_data)
        else:
            detector.fit(training_data)
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        # Create training record
        training_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        record = TrainingRecord(
            training_id=training_id,
            model_id="anomaly_detector",
            started_at=start_time.isoformat(),
            completed_at=end_time.isoformat(),
            duration_seconds=duration,
            training_samples=detector._n_samples,
            hyperparameters={
                "n_estimators": detector.config.n_estimators,
                "contamination": detector.config.contamination,
            },
            status="completed",
        )
        
        # Save training record
        try:
            store = get_model_store()
            store.save_training_record(record)
        except Exception as e:
            logger.warning(f"Failed to save training record: {e}")
        
        return jsonify({
            "ok": True,
            "training_id": training_id,
            "samples": detector._n_samples,
            "duration_seconds": round(duration, 3),
            "model_status": "fitted" if detector._is_fitted else "unfitted",
            "incremental": is_incremental,
        }), 200
        
    except Exception as e:
        logger.error(f"Model training failed: {e}")
        return jsonify({
            "error": "training_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/model/status", methods=["GET"])
def get_model_status():
    """
    Get current model status and configuration.
    
    Response:
    {
        "ok": true,
        "status": {
            "is_fitted": true,
            "n_samples": 1000,
            "n_estimators": 100,
            "contamination": 0.05,
            "feature_count": 25,
            "sensors_tracked": 5
        }
    }
    """
    try:
        detector = get_detector()
        
        status = {
            "is_fitted": detector._is_fitted,
            "n_samples": detector._n_samples,
            "n_estimators": detector.config.n_estimators,
            "contamination": detector.config.contamination,
            "feature_count": len(detector._feature_names or []) if detector._is_fitted else 0,
            "sensors_tracked": len(detector._sensor_stats),
            "config": {
                "n_estimators": detector.config.n_estimators,
                "contamination": detector.config.contamination,
                "max_samples": detector.config.max_samples,
                "max_features": detector.config.max_features,
                "bootstrap": detector.config.bootstrap,
                "warm_start": detector.config.warm_start,
            },
        }
        
        return jsonify({
            "ok": True,
            "status": status,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get model status: {e}")
        return jsonify({
            "error": "status_fetch_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/model/save", methods=["POST"])
def save_model():
    """
    Save the current model to disk.
    
    Request body (optional):
    {
        "path": "/custom/path/model.json",  # Custom save path
        "version": "1.0.0",  # Model version
        "metadata": {  # Additional metadata
            "description": "Model trained on March 2024 data",
            "tags": ["production", "v1"]
        }
    }
    
    Response:
    {
        "ok": true,
        "path": "/data/ml_models/anomaly_model.json",
        "version": "1.0.0"
    }
    """
    try:
        data, error_response = _get_json_object(required=False)
        if error_response:
            return error_response

        detector = get_detector()
        
        if not detector._is_fitted:
            return jsonify({
                "error": "model_not_fitted",
                "message": "Model must be fitted before saving",
            }), 400
        
        # Save using detector's built-in method
        custom_path = data.get("path")
        saved_path = detector.save_model(custom_path)
        
        # Also save to model store with versioning
        version = data.get("version", "1.0.0")

        metadata = data.get("metadata", {})
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            return _bad_request("'metadata' must be an object")
        
        try:
            store = get_model_store()
            
            # Prepare model data
            model_data = {
                "n_estimators": detector.config.n_estimators,
                "contamination": detector.config.contamination,
                "n_samples": detector._n_samples,
                "feature_names": detector._feature_names,
                "sensor_stats": detector._sensor_stats,
            }
            
            # Add scaler data if available
            if detector._scaler is not None:
                model_data["scaler"] = {
                    "mean": detector._scaler.mean_.tolist(),
                    "scale": detector._scaler.scale_.tolist(),
                }
            
            # Create metadata
            metadata = ModelMetadata(
                model_id="anomaly_detector",
                model_type="isolation_forest",
                version=version,
                created_at=datetime.now(timezone.utc).isoformat(),
                trained_at=datetime.now(timezone.utc).isoformat(),
                training_samples=detector._n_samples,
                feature_names=detector._feature_names or [],
                config={
                    "n_estimators": detector.config.n_estimators,
                    "contamination": detector.config.contamination,
                },
                description=metadata.get("description"),
                tags=metadata.get("tags", []),
            )
            
            store.save_model(
                model_id="anomaly_detector",
                version=version,
                model_data=model_data,
                metadata=metadata,
            )
            
        except Exception as e:
            logger.warning(f"Failed to save to model store: {e}")
        
        return jsonify({
            "ok": True,
            "path": saved_path,
            "version": version,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to save model: {e}")
        return jsonify({
            "error": "save_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/model/load", methods=["POST"])
def load_model():
    """
    Load a model from disk.
    
    Request body (optional):
    {
        "path": "/custom/path/model.json",  # Custom load path
        "version": "1.0.0"  # Specific version to load
    }
    
    Response:
    {
        "ok": true,
        "path": "/data/ml_models/anomaly_model.json",
        "version": "1.0.0",
        "samples": 1000
    }
    """
    try:
        data, error_response = _get_json_object(required=False)
        if error_response:
            return error_response

        detector = get_detector()
        
        # Load using detector's built-in method
        custom_path = data.get("path")
        detector.load_model(custom_path)
        
        # Try to load from model store if version specified
        version = data.get("version")
        if version:
            try:
                store = get_model_store()
                model_data, metadata = store.load_model("anomaly_detector", version)
                
                # Restore detector state from loaded model
                if "scaler" in model_data:
                    from sklearn.preprocessing import StandardScaler
                    detector._scaler = StandardScaler()
                    detector._scaler.mean_ = np.array(model_data["scaler"]["mean"])
                    detector._scaler.scale_ = np.array(model_data["scaler"]["scale"])
                
                detector._feature_names = model_data.get("feature_names")
                detector._sensor_stats = model_data.get("sensor_stats", {})
                detector._n_samples = model_data.get("n_samples", 0)
                detector._is_fitted = True
                
            except Exception as e:
                logger.warning(f"Failed to load from model store: {e}")
        
        return jsonify({
            "ok": True,
            "path": custom_path or detector.model_dir,
            "version": version or "latest",
            "samples": detector._n_samples,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return jsonify({
            "error": "load_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/model/versions", methods=["GET"])
def list_model_versions():
    """
    List all available model versions.
    
    Response:
    {
        "ok": true,
        "versions": [
            {
                "version": "1.0.0",
                "created_at": "2024-03-01T12:00:00Z",
                "samples": 1000,
                "status": "active"
            }
        ],
        "latest": "1.0.0"
    }
    """
    try:
        store = get_model_store()
        
        versions = store.list_versions("anomaly_detector")
        latest = store.get_latest_version("anomaly_detector")
        
        version_info = []
        for v in versions:
            try:
                _, metadata = store.load_model("anomaly_detector", v)
                version_info.append({
                    "version": v,
                    "created_at": metadata.created_at,
                    "samples": metadata.training_samples,
                    "status": metadata.status,
                })
            except Exception:
                version_info.append({"version": v, "status": "unknown"})
        
        return jsonify({
            "ok": True,
            "versions": version_info,
            "latest": latest,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to list model versions: {e}")
        return jsonify({
            "error": "list_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/compare", methods=["POST"])
def compare_models():
    """
    Compare multiple model versions.
    
    Request body:
    {
        "versions": ["1.0.0", "1.1.0"]
    }
    
    Response:
    {
        "ok": true,
        "comparison": {
            "model_id": "anomaly_detector",
            "versions": {...},
            "metrics_comparison": [...]
        }
    }
    """
    try:
        data, error_response = _get_json_object(required=True)
        if error_response:
            return error_response

        if "versions" not in data:
            return _bad_request("Request must include 'versions' array")

        if not isinstance(data["versions"], list) or not data["versions"]:
            return _bad_request("'versions' must be a non-empty array")

        if any(not isinstance(version, str) or not version.strip() for version in data["versions"]):
            return _bad_request("Each entry in 'versions' must be a non-empty string")

        store = get_model_store()
        comparison = store.compare_models("anomaly_detector", data["versions"])
        
        return jsonify({
            "ok": True,
            "comparison": comparison,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to compare models: {e}")
        return jsonify({
            "error": "compare_failed",
            "message": str(e),
        }), 500


@anomaly_bp.route("/anomaly/store/stats", methods=["GET"])
def get_store_stats():
    """
    Get model store statistics.
    
    Response:
    {
        "ok": true,
        "stats": {
            "total_models": 1,
            "total_versions": 3,
            "total_training_records": 10,
            "total_size_mb": 5.2
        }
    }
    """
    try:
        store = get_model_store()
        stats = store.get_store_stats()
        
        return jsonify({
            "ok": True,
            "stats": stats,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get store stats: {e}")
        return jsonify({
            "error": "stats_fetch_failed",
            "message": str(e),
        }), 500
