"""Multi-User Context Isolation API (Slice 148).

Per-user memory, preferences, and context isolation.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request, g
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

multi_user_bp = Blueprint("multi_user", __name__, url_prefix="/api/v1/user")


def _get_user_id() -> str:
    """Extract user ID from request."""
    # Try header first, then query param, then default
    user_id = request.headers.get("X-User-ID", request.args.get("user_id", "default"))
    return user_id


@multi_user_bp.route("/context", methods=["GET"])
def get_user_context():
    """Get current user context."""
    try:
        from copilot_core.multi_user.context_isolation import get_context_manager
        
        user_id = _get_user_id()
        ctx_manager = get_context_manager()
        ctx = ctx_manager.get_context(user_id, create=False)
        
        if ctx:
            return jsonify({
                "user_id": ctx.user_id,
                "preferences": ctx.preferences,
                "memory_keys": list(ctx.memory.keys()),
                "last_active": ctx.last_active,
            })
        else:
            return jsonify({"error": "No context found"}), 404
    except Exception as exc:
        _LOGGER.error("Failed to get user context: %s", exc)
        return jsonify({"error": str(exc)}), 500


@multi_user_bp.route("/preferences", methods=["PUT"])
def set_user_preference():
    """Set a user preference."""
    data = request.get_json()
    if not data or "key" not in data or "value" not in data:
        return jsonify({"error": "Missing 'key' or 'value'"}), 400
    
    try:
        from copilot_core.multi_user.context_isolation import get_context_manager
        
        user_id = _get_user_id()
        ctx_manager = get_context_manager()
        
        success = ctx_manager.set_preference(user_id, data["key"], data["value"])
        
        return jsonify({"success": success})
    except Exception as exc:
        _LOGGER.error("Failed to set preference: %s", exc)
        return jsonify({"error": str(exc)}), 500


@multi_user_bp.route("/memory", methods=["POST"])
def store_user_memory():
    """Store user-specific memory."""
    data = request.get_json()
    if not data or "key" not in data or "value" not in data:
        return jsonify({"error": "Missing 'key' or 'value'"}), 400
    
    try:
        from copilot_core.multi_user.context_isolation import get_context_manager
        
        user_id = _get_user_id()
        ctx_manager = get_context_manager()
        
        success = ctx_manager.store_memory(user_id, data["key"], data["value"])
        
        return jsonify({"success": success})
    except Exception as exc:
        _LOGGER.error("Failed to store memory: %s", exc)
        return jsonify({"error": str(exc)}), 500


@multi_user_bp.route("/context", methods=["DELETE"])
def delete_user_context():
    """Delete user context (GDPR compliance)."""
    try:
        from copilot_core.multi_user.context_isolation import get_context_manager
        
        user_id = _get_user_id()
        ctx_manager = get_context_manager()
        
        success = ctx_manager.delete_context(user_id)
        
        return jsonify({"success": success})
    except Exception as exc:
        _LOGGER.error("Failed to delete context: %s", exc)
        return jsonify({"error": str(exc)}), 500
