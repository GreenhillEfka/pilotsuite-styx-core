"""Intent Manager Admin API — Vertical Slice Phase 2.
Full CRUD + resolution for Intents.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from typing import Dict, List

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("intent_manager_admin", __name__, url_prefix="/api/v1")

# In-Memory Store
_intents: Dict[str, dict] = {}

@bp.route("/intents", methods=["GET"])
def list_intents():
    """List all Intents."""
    return jsonify({"ok": True, "intents": list(_intents.values()), "count": len(_intents)})

@bp.route("/intents", methods=["POST"])
def create_intent():
    """Create or update an Intent."""
    data = request.get_json() or {}
    intent_id = data.get("intent_id")
    if not intent_id:
        return jsonify({"ok": False, "error": "intent_id required"}), 400
    
    _intents[intent_id] = {
        "intent_id": intent_id,
        "name": data.get("name", intent_id),
        "trigger_phrases": data.get("trigger_phrases", []),
        "ha_script_id": data.get("ha_script_id"),
        "ha_blueprint_id": data.get("ha_blueprint_id"),
        "zone_ref": data.get("zone_ref"),
        "confidence_threshold": data.get("confidence_threshold", 0.8),
        "active": data.get("active", True)
    }
    _LOGGER.info(f"Created/updated Intent: {intent_id}")
    return jsonify({"ok": True, "intent": _intents[intent_id]})

@bp.route("/intents/<intent_id>", methods=["GET"])
def get_intent(intent_id):
    """Get single Intent detail."""
    intent = _intents.get(intent_id)
    if not intent:
        return jsonify({"ok": False, "error": "Intent not found"}), 404
    return jsonify({"ok": True, "intent": intent})

@bp.route("/intents/<intent_id>", methods=["DELETE"])
def delete_intent(intent_id):
    """Delete an Intent."""
    if intent_id in _intents:
        del _intents[intent_id]
        _LOGGER.info(f"Deleted Intent: {intent_id}")
        return jsonify({"ok": True, "deleted": intent_id})
    return jsonify({"ok": False, "error": "Intent not found"}), 404

@bp.route("/intents/resolve", methods=["POST"])
def resolve_intent():
    """Resolve a phrase to an Intent."""
    data = request.get_json() or {}
    phrase = data.get("phrase", "").lower()
    
    if not phrase:
        return jsonify({"ok": False, "error": "phrase required"}), 400
    
    # Simple keyword matching (would be ML-based in production)
    best_match = None
    best_score = 0
    
    for intent in _intents.values():
        if not intent.get("active", True):
            continue
        
        for trigger in intent.get("trigger_phrases", []):
            if trigger.lower() in phrase or phrase in trigger.lower():
                score = 1.0
                if score > best_score:
                    best_score = score
                    best_match = intent
    
    if best_match and best_score >= best_match.get("confidence_threshold", 0.8):
        return jsonify({
            "ok": True,
            "resolved": True,
            "intent": best_match,
            "confidence": best_score
        })
    
    return jsonify({"ok": True, "resolved": False, "confidence": 0})

@bp.route("/intents/active", methods=["GET"])
def get_active_intents():
    """Get all active Intents."""
    active = [i for i in _intents.values() if i.get("active", True)]
    return jsonify({"ok": True, "active_intents": active, "count": len(active)})

@bp.route("/intents/summary", methods=["GET"])
def intents_summary():
    """Get summary of all Intents."""
    total = len(_intents)
    active = sum(1 for i in _intents.values() if i.get("active", True))
    with_script = sum(1 for i in _intents.values() if i.get("ha_script_id"))
    
    return jsonify({
        "ok": True,
        "summary": {
            "total_intents": total,
            "active_intents": active,
            "intents_with_script": with_script
        }
    })
