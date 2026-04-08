"""
ML Forecast API Blueprint for PilotSuite Styx Core

Provides REST API endpoints for:
- Time series forecasting (LSTM, Transformer)
- Model management (create, train, list, delete)
- Training pipeline control
- Experiment tracking
- A/B testing

Usage:
    from copilot_core.api.v1.ml_forecast import ml_forecast_bp
    app.register_blueprint(ml_forecast_bp, url_prefix='/api/v1')
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Try to import ML modules
try:
    from copilot_core.ml.lstm_forecast import LSTMForecastManager, forecast_temperature
    from copilot_core.ml.transformer_model import TransformerForecastManager
    from copilot_core.ml.training_pipeline import TrainingPipeline, TrainingConfig
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    logger.warning(f"ML modules not available: {e}")


# Create blueprint
ml_forecast_bp = Blueprint("ml_forecast", __name__)


# Initialize managers (lazy loading)
_lstm_manager = None
_transformer_manager = None
_training_pipeline = None


def get_lstm_manager() -> Optional[LSTMForecastManager]:
    """Get or create LSTM manager."""
    global _lstm_manager
    if not ML_AVAILABLE:
        return None
    if _lstm_manager is None:
        _lstm_manager = LSTMForecastManager()
    return _lstm_manager


def get_transformer_manager() -> Optional[TransformerForecastManager]:
    """Get or create transformer manager."""
    global _transformer_manager
    if not ML_AVAILABLE:
        return None
    if _transformer_manager is None:
        _transformer_manager = TransformerForecastManager()
    return _transformer_manager


def get_training_pipeline() -> Optional[TrainingPipeline]:
    """Get or create training pipeline."""
    global _training_pipeline
    if not ML_AVAILABLE:
        return None
    if _training_pipeline is None:
        _training_pipeline = TrainingPipeline()
    return _training_pipeline


# ============================================================================
# Health & Status
# ============================================================================

@ml_forecast_bp.route("/ml/status", methods=["GET"])
def ml_status():
    """
    Get ML system status.
    
    Returns:
        ML system availability and loaded models
    """
    status = {
        "ml_available": ML_AVAILABLE,
        "lstm_models": 0,
        "transformer_models": 0,
        "active_experiments": 0
    }
    
    if ML_AVAILABLE:
        lstm_mgr = get_lstm_manager()
        if lstm_mgr:
            status["lstm_models"] = len(lstm_mgr.list_models())
        
        transformer_mgr = get_transformer_manager()
        if transformer_mgr:
            status["transformer_models"] = len(transformer_mgr.list_models())
        
        pipeline = get_training_pipeline()
        if pipeline:
            status["active_experiments"] = len(pipeline.tracker.experiments)
    
    return jsonify(status), 200


# ============================================================================
# LSTM Forecasting Endpoints
# ============================================================================

@ml_forecast_bp.route("/ml/lstm/models", methods=["GET"])
def list_lstm_models():
    """
    List all LSTM models.
    
    Returns:
        List of LSTM models with metadata
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    manager = get_lstm_manager()
    if not manager:
        return jsonify({"error": "LSTM manager not initialized"}), 503
    
    models = manager.list_models()
    return jsonify({
        "models": models,
        "count": len(models)
    }), 200


@ml_forecast_bp.route("/ml/lstm/models", methods=["POST"])
def create_lstm_model():
    """
    Create new LSTM model.
    
    Request JSON:
        {
            "horizon": "1h"|"6h"|"24h"|"7d",
            "hidden_size": 64,
            "num_layers": 2,
            "seq_length": 48,
            "input_features": 1,
            "dropout": 0.2,
            "bidirectional": false
        }
    
    Returns:
        Created model name and configuration
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    data = request.get_json() or {}
    
    try:
        manager = get_lstm_manager()
        model_name = manager.create_model(
            horizon=data.get("horizon", "1h"),
            hidden_size=data.get("hidden_size", 64),
            num_layers=data.get("num_layers", 2),
            seq_length=data.get("seq_length"),
            input_features=data.get("input_features"),
            dropout=data.get("dropout", 0.2),
            bidirectional=data.get("bidirectional", False)
        )
        
        return jsonify({
            "model_name": model_name,
            "config": manager.model_metadata[model_name],
            "message": "Model created successfully"
        }), 201
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create LSTM model: {e}")
        return jsonify({"error": "model_creation_failed", "message": str(e)}), 500


@ml_forecast_bp.route("/ml/lstm/models/<model_name>/train", methods=["POST"])
def train_lstm_model(model_name: str):
    """
    Train LSTM model.
    
    Request JSON:
        {
            "train_data": [[val1], [val2], ...],  # 2D array
            "val_data": [[val1], [val2], ...],
            "epochs": 50,
            "batch_size": 32,
            "learning_rate": 0.001,
            "early_stopping_patience": 10,
            "save_checkpoint": true
        }
    
    Returns:
        Training results and metrics
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    import numpy as np
    data = request.get_json() or {}
    
    try:
        train_data = data.get("train_data")
        if train_data is None:
            return jsonify({"error": "train_data is required"}), 400
        
        train_data = np.array(train_data)
        
        val_data = data.get("val_data")
        if val_data is not None:
            val_data = np.array(val_data)
        
        manager = get_lstm_manager()
        
        results = manager.train_model(
            model_name=model_name,
            train_data=train_data,
            val_data=val_data,
            epochs=data.get("epochs", 50),
            batch_size=data.get("batch_size", 32),
            learning_rate=data.get("learning_rate", 0.001),
            early_stopping_patience=data.get("early_stopping_patience", 10),
            save_checkpoint=data.get("save_checkpoint", True)
        )
        
        return jsonify({
            "model_name": model_name,
            "training_results": results,
            "message": "Training completed successfully"
        }), 200
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to train LSTM model {model_name}: {e}")
        return jsonify({"error": "training_failed", "message": str(e)}), 500


@ml_forecast_bp.route("/ml/lstm/models/<model_name>/predict", methods=["POST"])
def predict_lstm(model_name: str):
    """
    Make LSTM prediction.
    
    Request JSON:
        {
            "input_sequence": [[val1], [val2], ...],
            "with_uncertainty": true,
            "n_samples": 100,
            "confidence_level": 0.95
        }
    
    Returns:
        Forecast predictions with confidence intervals
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    import numpy as np
    data = request.get_json() or {}
    
    try:
        input_sequence = data.get("input_sequence")
        if input_sequence is None:
            return jsonify({"error": "input_sequence is required"}), 400
        
        input_sequence = np.array(input_sequence)
        
        manager = get_lstm_manager()
        
        result = manager.predict(
            model_name=model_name,
            input_sequence=input_sequence,
            with_uncertainty=data.get("with_uncertainty", True),
            n_samples=data.get("n_samples", 100),
            confidence_level=data.get("confidence_level", 0.95)
        )
        
        return jsonify(result), 200
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to predict with LSTM {model_name}: {e}")
        return jsonify({"error": "prediction_failed", "message": str(e)}), 500


@ml_forecast_bp.route("/ml/lstm/models/<model_name>", methods=["DELETE"])
def delete_lstm_model(model_name: str):
    """
    Delete LSTM model.
    
    Query params:
        - delete_all_versions: true|false
    
    Returns:
        Deletion confirmation
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    delete_all = request.args.get("delete_all_versions", "false").lower() == "true"
    
    try:
        manager = get_lstm_manager()
        manager.delete_model(model_name, delete_all_versions=delete_all)
        
        return jsonify({
            "model_name": model_name,
            "deleted": True,
            "all_versions": delete_all
        }), 200
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to delete LSTM model {model_name}: {e}")
        return jsonify({"error": "deletion_failed", "message": str(e)}), 500


# ============================================================================
# Transformer Forecasting Endpoints
# ============================================================================

@ml_forecast_bp.route("/ml/transformer/models", methods=["GET"])
def list_transformer_models():
    """List all transformer models."""
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    manager = get_transformer_manager()
    if not manager:
        return jsonify({"error": "Transformer manager not initialized"}), 503
    
    models = manager.list_models()
    return jsonify({
        "models": models,
        "count": len(models)
    }), 200


@ml_forecast_bp.route("/ml/transformer/models", methods=["POST"])
def create_transformer_model():
    """
    Create new transformer model.
    
    Request JSON:
        {
            "horizon": "24h"|"48h"|"7d"|"30d",
            "d_model": 64,
            "nhead": 4,
            "num_encoder_layers": 3,
            "dim_feedforward": 128,
            "seq_length": 96,
            "input_features": 1,
            "dropout": 0.1,
            "activation": "relu"|"gelu",
            "model_name": "custom_name"
        }
    
    Returns:
        Created model configuration
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    data = request.get_json() or {}
    
    try:
        manager = get_transformer_manager()
        model_name = manager.create_model(
            horizon=data.get("horizon", "24h"),
            d_model=data.get("d_model", 64),
            nhead=data.get("nhead", 4),
            num_encoder_layers=data.get("num_encoder_layers", 3),
            dim_feedforward=data.get("dim_feedforward", 128),
            seq_length=data.get("seq_length"),
            input_features=data.get("input_features"),
            dropout=data.get("dropout", 0.1),
            activation=data.get("activation", "relu"),
            model_name=data.get("model_name")
        )
        
        return jsonify({
            "model_name": model_name,
            "config": manager.model_metadata[model_name],
            "message": "Transformer model created successfully"
        }), 201
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create transformer model: {e}")
        return jsonify({"error": "model_creation_failed", "message": str(e)}), 500


@ml_forecast_bp.route("/ml/transformer/models/<model_name>/train", methods=["POST"])
def train_transformer_model(model_name: str):
    """
    Train transformer model.
    
    Request JSON:
        {
            "train_data": [[val1], [val2], ...],
            "val_data": [[val1], [val2], ...],
            "epochs": 100,
            "batch_size": 32,
            "learning_rate": 0.0005,
            "early_stopping_patience": 15,
            "gradient_clip": 1.0
        }
    
    Returns:
        Training results
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    import numpy as np
    data = request.get_json() or {}
    
    try:
        train_data = data.get("train_data")
        if train_data is None:
            return jsonify({"error": "train_data is required"}), 400
        
        train_data = np.array(train_data)
        
        val_data = data.get("val_data")
        if val_data is not None:
            val_data = np.array(val_data)
        
        manager = get_transformer_manager()
        
        results = manager.train_model(
            model_name=model_name,
            train_data=train_data,
            val_data=val_data,
            epochs=data.get("epochs", 100),
            batch_size=data.get("batch_size", 32),
            learning_rate=data.get("learning_rate", 0.0005),
            early_stopping_patience=data.get("early_stopping_patience", 15),
            gradient_clip=data.get("gradient_clip", 1.0)
        )
        
        return jsonify({
            "model_name": model_name,
            "training_results": results,
            "message": "Training completed successfully"
        }), 200
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to train transformer {model_name}: {e}")
        return jsonify({"error": "training_failed", "message": str(e)}), 500


@ml_forecast_bp.route("/ml/transformer/models/<model_name>/predict", methods=["POST"])
def predict_transformer(model_name: str):
    """
    Make transformer prediction.
    
    Request JSON:
        {
            "input_sequence": [[val1], [val2], ...],
            "return_attention": false
        }
    
    Returns:
        Forecast predictions
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    import numpy as np
    data = request.get_json() or {}
    
    try:
        input_sequence = data.get("input_sequence")
        if input_sequence is None:
            return jsonify({"error": "input_sequence is required"}), 400
        
        input_sequence = np.array(input_sequence)
        
        manager = get_transformer_manager()
        
        result = manager.predict(
            model_name=model_name,
            input_sequence=input_sequence,
            return_attention=data.get("return_attention", False)
        )
        
        return jsonify(result), 200
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to predict with transformer {model_name}: {e}")
        return jsonify({"error": "prediction_failed", "message": str(e)}), 500


# ============================================================================
# A/B Testing Endpoints
# ============================================================================

@ml_forecast_bp.route("/ml/ab-tests", methods=["GET"])
def list_ab_tests():
    """List all A/B tests."""
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    manager = get_transformer_manager()
    if not manager:
        return jsonify({"error": "Manager not initialized"}), 503
    
    return jsonify({
        "ab_tests": manager.ab_tests,
        "count": len(manager.ab_tests)
    }), 200


@ml_forecast_bp.route("/ml/ab-tests", methods=["POST"])
def create_ab_test():
    """
    Create A/B test.
    
    Request JSON:
        {
            "test_name": "energy_forecast_test",
            "model_a": "transformer_24h_v1",
            "model_b": "transformer_24h_v2",
            "traffic_split": 0.5
        }
    
    Returns:
        Created test configuration
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    data = request.get_json() or {}
    
    required = ["test_name", "model_a", "model_b"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400
    
    try:
        manager = get_transformer_manager()
        
        manager.setup_ab_test(
            test_name=data["test_name"],
            model_a=data["model_a"],
            model_b=data["model_b"],
            traffic_split=data.get("traffic_split", 0.5)
        )
        
        return jsonify({
            "test_name": data["test_name"],
            "config": manager.ab_tests[data["test_name"]],
            "message": "A/B test created successfully"
        }), 201
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create A/B test: {e}")
        return jsonify({"error": "test_creation_failed", "message": str(e)}), 500


@ml_forecast_bp.route("/ml/ab-tests/<test_name>/predict", methods=["POST"])
def predict_ab_test(test_name: str):
    """
    Make prediction using A/B test routing.
    
    Request JSON:
        {
            "input_sequence": [[val1], [val2], ...]
        }
    
    Returns:
        Prediction from routed model with model info
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    import numpy as np
    data = request.get_json() or {}
    
    try:
        input_sequence = data.get("input_sequence")
        if input_sequence is None:
            return jsonify({"error": "input_sequence is required"}), 400
        
        input_sequence = np.array(input_sequence)
        
        manager = get_transformer_manager()
        result = manager.predict_ab_test(test_name, input_sequence)
        
        return jsonify(result), 200
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed A/B test prediction {test_name}: {e}")
        return jsonify({"error": "prediction_failed", "message": str(e)}), 500


# ============================================================================
# Training Pipeline Endpoints
# ============================================================================

@ml_forecast_bp.route("/ml/experiments", methods=["GET"])
def list_experiments():
    """
    List training experiments.
    
    Query params:
        - model_name: Filter by model
        - status: Filter by status
    
    Returns:
        List of experiments
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    pipeline = get_training_pipeline()
    if not pipeline:
        return jsonify({"error": "Pipeline not initialized"}), 503
    
    model_name = request.args.get("model_name")
    status = request.args.get("status")
    
    experiments = pipeline.tracker.list_experiments(
        model_name=model_name,
        status=status
    )
    
    return jsonify({
        "experiments": experiments,
        "count": len(experiments)
    }), 200


@ml_forecast_bp.route("/ml/experiments/<experiment_id>", methods=["GET"])
def get_experiment(experiment_id: str):
    """Get experiment details."""
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    pipeline = get_training_pipeline()
    if not pipeline:
        return jsonify({"error": "Pipeline not initialized"}), 503
    
    try:
        exp = pipeline.tracker.get_experiment(experiment_id)
        return jsonify(exp), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@ml_forecast_bp.route("/ml/checkpoints", methods=["GET"])
def list_checkpoints():
    """
    List available checkpoints.
    
    Query params:
        - model_name: Filter by model
    
    Returns:
        List of checkpoints
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    pipeline = get_training_pipeline()
    if not pipeline:
        return jsonify({"error": "Pipeline not initialized"}), 503
    
    model_name = request.args.get("model_name")
    checkpoints = pipeline.list_checkpoints(model_name=model_name)
    
    return jsonify({
        "checkpoints": checkpoints,
        "count": len(checkpoints)
    }), 200


# ============================================================================
# Quick Forecast Endpoint
# ============================================================================

@ml_forecast_bp.route("/ml/forecast/temperature", methods=["POST"])
def quick_temperature_forecast():
    """
    Quick temperature forecast endpoint.
    
    Request JSON:
        {
            "temperature_history": [t1, t2, t3, ...],
            "horizon": "1h"|"6h"|"24h"|"7d"
        }
    
    Returns:
        Temperature forecast with confidence intervals
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    import numpy as np
    data = request.get_json() or {}
    
    try:
        temp_history = data.get("temperature_history")
        if temp_history is None:
            return jsonify({"error": "temperature_history is required"}), 400
        
        temp_history = np.array(temp_history)
        horizon = data.get("horizon", "1h")
        
        result = forecast_temperature(
            temperature_history=temp_history,
            horizon=horizon
        )
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Failed temperature forecast: {e}")
        return jsonify({"error": "forecast_failed", "message": str(e)}), 500


# ============================================================================
# Model Export/Import
# ============================================================================

@ml_forecast_bp.route("/ml/models/<model_name>/export", methods=["GET"])
def export_model(model_name: str):
    """
    Export model for deployment.
    
    Query params:
        - format: "pt"|"onnx" (default: pt)
        - version: specific version (default: latest)
    
    Returns:
        Model file path and metadata
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    export_format = request.args.get("format", "pt")
    version = request.args.get("version")
    
    try:
        # Try LSTM first
        lstm_mgr = get_lstm_manager()
        if model_name in lstm_mgr.models:
            lstm_mgr.save_model(model_name, version=int(version) if version else None)
            metadata = lstm_mgr.model_metadata[model_name]
            return jsonify({
                "model_name": model_name,
                "model_type": "lstm",
                "export_path": metadata.get("model_path"),
                "metadata": metadata
            }), 200
        
        # Try transformer
        transformer_mgr = get_transformer_manager()
        if model_name in transformer_mgr.models:
            transformer_mgr.save_model(model_name, version=int(version) if version else None)
            metadata = transformer_mgr.model_metadata[model_name]
            return jsonify({
                "model_name": model_name,
                "model_type": "transformer",
                "export_path": metadata.get("model_path"),
                "metadata": metadata
            }), 200
        
        return jsonify({"error": f"Model {model_name} not found"}), 404
    
    except Exception as e:
        logger.error(f"Failed to export model {model_name}: {e}")
        return jsonify({"error": "export_failed", "message": str(e)}), 500


@ml_forecast_bp.route("/ml/models/<model_name>/load", methods=["POST"])
def load_model_endpoint(model_name: str):
    """
    Load model from disk.
    
    Query params:
        - version: specific version (default: latest)
    
    Returns:
        Loaded model metadata
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML not available"}), 503
    
    version = request.args.get("version")
    
    try:
        # Try LSTM
        lstm_mgr = get_lstm_manager()
        try:
            loaded_name = lstm_mgr.load_model(model_name, version=int(version) if version else None)
            return jsonify({
                "model_name": loaded_name,
                "model_type": "lstm",
                "metadata": lstm_mgr.model_metadata[loaded_name]
            }), 200
        except ValueError:
            pass
        
        # Try transformer
        transformer_mgr = get_transformer_manager()
        try:
            loaded_name = transformer_mgr.load_model(model_name, version=int(version) if version else None)
            return jsonify({
                "model_name": loaded_name,
                "model_type": "transformer",
                "metadata": transformer_mgr.model_metadata[loaded_name]
            }), 200
        except ValueError:
            pass
        
        return jsonify({"error": f"Model {model_name} not found on disk"}), 404
    
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {e}")
        return jsonify({"error": "load_failed", "message": str(e)}), 500
