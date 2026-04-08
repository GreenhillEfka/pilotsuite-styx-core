"""ML Pipeline API — Training, Inference, and Model Management.

Endpoints:
  GET  /api/v1/ml/status             — Pipeline status (models, training, inference)
  POST /api/v1/ml/train/:model_name  — Train a registered model
  POST /api/v1/ml/predict/:model_name — Run inference on a model
  GET  /api/v1/ml/models              — List registered models
  POST /api/v1/ml/models/:name/load   — Load model from disk
  GET  /api/v1/ml/inference/stats     — Inference engine statistics
"""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

bp = Blueprint("ml_pipeline", __name__, url_prefix="/api/v1/ml")
_LOGGER = logging.getLogger(__name__)


def _services():
    return current_app.config.get("COPILOT_SERVICES", {})


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@bp.route("/status", methods=["GET"])
def status():
    """Combined ML pipeline status."""
    s = _services()
    result = {"ok": True}

    tp = s.get("training_pipeline")
    if tp:
        result["training"] = tp.get_training_status()

    ie = s.get("inference_engine")
    if ie:
        result["inference"] = ie.get_statistics()

    return jsonify(result)


@bp.route("/models", methods=["GET"])
def list_models():
    """List registered models across training + inference."""
    s = _services()
    models = {}

    tp = s.get("training_pipeline")
    if tp:
        for name, info in tp._model_classes.items():
            models[name] = {
                "registered": True,
                "feature_names": info.get("feature_names", []),
                "metrics": tp.model_metrics.get(name, {}),
            }

    ie = s.get("inference_engine")
    if ie:
        for name in ie.models:
            if name not in models:
                models[name] = {}
            models[name]["loaded_for_inference"] = True

    return jsonify({"ok": True, "models": models})


@bp.route("/train/<model_name>", methods=["POST"])
def train(model_name):
    """Train a registered model."""
    tp = _services().get("training_pipeline")
    if not tp:
        return jsonify({"ok": False, "error": "training_pipeline not initialized"}), 503

    result = tp.train_model(model_name)
    ok = result.get("status") == "success"
    return jsonify({"ok": ok, **result}), 200 if ok else 400


@bp.route("/predict/<model_name>", methods=["POST"])
def predict(model_name):
    """Run inference on a loaded model."""
    ie = _services().get("inference_engine")
    if not ie:
        return jsonify({"ok": False, "error": "inference_engine not initialized"}), 503

    data = request.get_json(silent=True) or {}
    features = data.get("features", {})
    if not features:
        return jsonify({"ok": False, "error": "features required"}), 400

    result = ie.predict(model_name, features)
    ok = result.get("status") == "success"
    return jsonify({"ok": ok, **result}), 200 if ok else 400


@bp.route("/models/<model_name>/load", methods=["POST"])
def load_model(model_name):
    """Load a model from disk into inference engine."""
    ie = _services().get("inference_engine")
    if not ie:
        return jsonify({"ok": False, "error": "inference_engine not initialized"}), 503

    success = ie.load_model(model_name)
    return jsonify({"ok": success, "model": model_name})


@bp.route("/inference/stats", methods=["GET"])
def inference_stats():
    """Get inference engine statistics."""
    ie = _services().get("inference_engine")
    if not ie:
        return jsonify({"ok": False, "error": "inference_engine not initialized"}), 503
    return jsonify({"ok": True, **ie.get_statistics()})
