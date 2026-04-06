"""Learning Memory Admin API — Vertical Slice Phase 2.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("learning_memory_admin", __name__, url_prefix="/api/v1/memory")

_patterns = []

@bp.route("/patterns", methods=["GET"])
def list_patterns():
    return jsonify({"ok": True, "patterns": _patterns, "count": len(_patterns)})

@bp.route("/patterns/store", methods=["POST"])
def store_pattern():
    data = request.get_json() or {}
    pattern = {
        "pattern_id": data.get("pattern_id"),
        "context": data.get("context"),
        "frequency": data.get("frequency", 1),
        "confidence": data.get("confidence", 0.5),
        "learned_at": "now"
    }
    _patterns.append(pattern)
    return jsonify({"ok": True, "pattern_id": pattern["pattern_id"]})

@bp.route("/suggest", methods=["GET"])
def get_suggestions():
    # Return top patterns by confidence
    top = sorted(_patterns, key=lambda p: p.get("confidence", 0), reverse=True)[:5]
    return jsonify({"ok": True, "suggestions": top})
