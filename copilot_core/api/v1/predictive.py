"""Predictive Automation API Endpoints — v1.0.0.

REST API für prädiktive Automation:
- GET /api/v1/predictive/patterns — Gelernte Muster
- GET /api/v1/predictive/next — Nächste vorhergesagte Aktion
- POST /api/v1/predictive/confirm — Vorhersage bestätigen
- POST /api/v1/predictive/reject — Vorhersage ablehnen
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request, current_app

from copilot_core.api.security import require_token
from copilot_core.automation.pattern_learner import PatternLearner
from copilot_core.automation.predictor import (
    PredictiveAutomationEngine,
    PredictionRequest
)

_LOGGER = logging.getLogger(__name__)

predictive_bp = Blueprint("predictive", __name__, url_prefix="/api/v1/predictive")


def _get_pattern_learner() -> PatternLearner:
    """Hole PatternLearner aus App Config oder erstelle neue Instanz."""
    try:
        services = current_app.config.get("COPILOT_SERVICES", {})
        pattern_learner = services.get("pattern_learner")
        
        if pattern_learner:
            return pattern_learner
        
        # Fallback: Neue Instanz erstellen
        data_dir = current_app.config.get("COPILOT_CFG").data_dir
        return PatternLearner(data_dir=data_dir)
    except Exception as e:
        _LOGGER.warning(f"Error getting pattern learner: {e}")
        # Default fallback
        return PatternLearner()


def _get_predictor() -> PredictiveAutomationEngine:
    """Hole PredictiveEngine aus App Config oder erstelle neue Instanz."""
    try:
        services = current_app.config.get("COPILOT_SERVICES", {})
        predictor = services.get("predictive_engine")
        
        if predictor:
            return predictor
        
        # Fallback: Neue Instanz erstellen
        pattern_learner = _get_pattern_learner()
        return PredictiveAutomationEngine(pattern_learner)
    except Exception as e:
        _LOGGER.warning(f"Error getting predictor: {e}")
        # Default fallback
        pattern_learner = PatternLearner()
        return PredictiveAutomationEngine(pattern_learner)


@predictive_bp.route("/patterns", methods=["GET"])
@require_token
def get_patterns():
    """Hole gelernte Muster.
    
    Query Params:
    - type: Filter nach Pattern-Typ ("time_based", "weather_based", etc.)
    - entity_id: Filter nach Entity ID
    - min_confidence: Minimale Confidence (default: 0.0)
    - limit: Maximale Anzahl zurückgegebener Muster (default: 50)
    
    Returns:
    {
        "ok": true,
        "patterns": [...],
        "stats": {...},
        "count": 10
    }
    """
    try:
        pattern_learner = _get_pattern_learner()
        
        # Parse Query Params
        pattern_type = request.args.get("type")
        entity_id = request.args.get("entity_id")
        min_confidence = float(request.args.get("min_confidence", 0.0))
        limit = int(request.args.get("limit", 50))
        
        # Hole Patterns
        patterns = pattern_learner.get_patterns(
            pattern_type=pattern_type,
            entity_id=entity_id,
            min_confidence=min_confidence
        )
        
        # Begrenze Anzahl
        patterns = patterns[:limit]
        
        # Hole Stats
        stats = pattern_learner.get_pattern_stats()
        
        return jsonify({
            "ok": True,
            "patterns": [p.to_dict() for p in patterns],
            "stats": {
                "total_patterns": stats.total_patterns,
                "time_based_patterns": stats.time_based_patterns,
                "weather_based_patterns": stats.weather_based_patterns,
                "sequence_patterns": stats.sequence_patterns,
                "device_patterns": stats.device_patterns,
                "avg_confidence": stats.avg_confidence,
                "total_observations": stats.total_observations,
            },
            "count": len(patterns),
            "generated_at": datetime.now().isoformat()
        })
    
    except Exception as e:
        _LOGGER.error(f"Error getting patterns: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@predictive_bp.route("/next", methods=["GET"])
@require_token
def get_next_prediction():
    """Hole nächste vorhergesagte Aktion.
    
    Query Params:
    - weather: Aktuelle Wetterbedingung ("sunny", "cloudy", "rainy")
    - temperature: Aktuelle Temperatur (°C)
    - include_low_confidence: Auch niedrige Confidence einschließen (default: false)
    - max_predictions: Maximale Anzahl Vorhersagen (default: 1)
    
    Returns:
    {
        "ok": true,
        "prediction": {...},
        "all_predictions": [...],
        "generated_at": "..."
    }
    """
    try:
        predictor = _get_predictor()
        
        # Parse Query Params
        weather = request.args.get("weather")
        temperature = request.args.get("temperature", type=float)
        include_low = request.args.get("include_low_confidence", "false").lower() == "true"
        max_predictions = int(request.args.get("max_predictions", 1))
        
        # Erstelle Request
        prediction_request = PredictionRequest(
            current_time=datetime.now(),
            weather_condition=weather,
            current_temperature=temperature,
            include_low_confidence=include_low,
            max_predictions=max_predictions
        )
        
        # Hole Vorhersage(n)
        if max_predictions == 1:
            prediction = predictor.predict_next(prediction_request)
            all_predictions = [prediction] if prediction else []
        else:
            all_predictions = predictor.predict_all(prediction_request)
            prediction = all_predictions[0] if all_predictions else None
        
        return jsonify({
            "ok": True,
            "prediction": prediction.to_dict() if prediction else None,
            "all_predictions": [p.to_dict() for p in all_predictions],
            "count": len(all_predictions),
            "generated_at": datetime.now().isoformat()
        })
    
    except Exception as e:
        _LOGGER.error(f"Error getting next prediction: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@predictive_bp.route("/confirm", methods=["POST"])
@require_token
def confirm_prediction():
    """Bestätige eine Vorhersage.
    
    Request Body:
    {
        "prediction_id": "pred_000001",
        "action_performed": true  // Optional: wurde Aktion ausgeführt?
    }
    
    Returns:
    {
        "ok": true,
        "prediction_id": "pred_000001",
        "confirmed": true,
        "message": "..."
    }
    """
    try:
        predictor = _get_predictor()
        
        # Parse Request Body
        data = request.get_json() or {}
        prediction_id = data.get("prediction_id")
        action_performed = data.get("action_performed", True)
        
        if not prediction_id:
            return jsonify({
                "ok": False,
                "error": "prediction_id required"
            }), 400
        
        # Bestätige Vorhersage
        result = predictor.confirm_prediction(
            prediction_id=prediction_id,
            actual_action_performed=action_performed
        )
        
        return jsonify(result)
    
    except Exception as e:
        _LOGGER.error(f"Error confirming prediction: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@predictive_bp.route("/reject", methods=["POST"])
@require_token
def reject_prediction():
    """Lehne eine Vorhersage ab.
    
    Request Body:
    {
        "prediction_id": "pred_000001",
        "reason": "Falsche Vorhersage"  // Optional
    }
    
    Returns:
    {
        "ok": true,
        "prediction_id": "pred_000001",
        "rejected": true,
        "reason": "...",
        "message": "..."
    }
    """
    try:
        predictor = _get_predictor()
        
        # Parse Request Body
        data = request.get_json() or {}
        prediction_id = data.get("prediction_id")
        reason = data.get("reason")
        
        if not prediction_id:
            return jsonify({
                "ok": False,
                "error": "prediction_id required"
            }), 400
        
        # Lehne Vorhersage ab
        result = predictor.reject_prediction(
            prediction_id=prediction_id,
            reason=reason
        )
        
        return jsonify(result)
    
    except Exception as e:
        _LOGGER.error(f"Error rejecting prediction: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@predictive_bp.route("/stats", methods=["GET"])
@require_token
def get_predictive_stats():
    """Hole Statistik über prädiktive Automation.
    
    Returns:
    {
        "ok": true,
        "stats": {...},
        "generated_at": "..."
    }
    """
    try:
        predictor = _get_predictor()
        stats = predictor.get_prediction_stats()
        
        return jsonify({
            "ok": True,
            "stats": stats,
            "generated_at": datetime.now().isoformat()
        })
    
    except Exception as e:
        _LOGGER.error(f"Error getting predictive stats: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@predictive_bp.route("/observe", methods=["POST"])
@require_token
def observe_action():
    """Registriere Beobachtung für Pattern-Learning.
    
    Request Body:
    {
        "entity_id": "light.wohnzimmer",
        "action": "turn_on",
        "timestamp": "2026-03-02T08:00:00",  // Optional, default: now
        "context": {  // Optional
            "weather_condition": "sunny",
            "temperature": 22.5,
            "related_entities": ["switch.tv"]
        }
    }
    
    Returns:
    {
        "ok": true,
        "message": "Beobachtung registriert",
        "patterns_updated": 2
    }
    """
    try:
        pattern_learner = _get_pattern_learner()
        
        # Parse Request Body
        data = request.get_json() or {}
        entity_id = data.get("entity_id")
        action = data.get("action")
        timestamp_str = data.get("timestamp")
        context = data.get("context", {})
        
        if not entity_id or not action:
            return jsonify({
                "ok": False,
                "error": "entity_id and action required"
            }), 400
        
        # Parse Timestamp
        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": "Invalid timestamp format"
                }), 400
        
        # Registriere Beobachtung
        pattern_count_before = len(pattern_learner.patterns)
        pattern_learner.observe(
            entity_id=entity_id,
            action=action,
            timestamp=timestamp,
            context=context
        )
        pattern_count_after = len(pattern_learner.patterns)
        
        return jsonify({
            "ok": True,
            "message": "Beobachtung registriert",
            "patterns_updated": pattern_count_after - pattern_count_before,
            "total_patterns": pattern_count_after
        })
    
    except Exception as e:
        _LOGGER.error(f"Error observing action: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500
