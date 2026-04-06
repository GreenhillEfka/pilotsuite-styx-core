"""User Preferences API v1 for Multi-User Preference Learning (P1-003).

Provides REST API endpoints for preference CRUD operations:
- GET /api/v1/preferences/{user_id} - Get all preferences for a user
- GET /api/v1/preferences/{user_id}/{key} - Get specific preference
- POST /api/v1/preferences/{user_id} - Create/update preference
- PUT /api/v1/preferences/{user_id}/{key} - Update specific preference
- DELETE /api/v1/preferences/{user_id}/{key} - Delete specific preference
- DELETE /api/v1/preferences/{user_id} - Delete all user preferences

Privacy-first: all data remains local.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, jsonify, request

from copilot_core.user_profiles import get_user_profiles, UserProfiles
from copilot_core.preference_learning import get_preference_learner, PreferenceLearner

bp = Blueprint("preferences", __name__, url_prefix="/preferences")
preferences_bp = bp

_LOGGER = logging.getLogger(__name__)


def _get_learner() -> PreferenceLearner:
    """Get the preference learner instance."""
    return get_preference_learner()


def _get_profiles() -> UserProfiles:
    """Get the user profiles instance."""
    return get_user_profiles()


def _require_auth():
    """Validate authentication token."""
    from copilot_core.api.security import validate_token
    from flask import request
    if not validate_token(request):
        return False
    return True


@bp.before_request
def _check_auth():
    """Require authentication for all preference endpoints."""
    if not _require_auth():
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required"
        }), 401


# ==================== User Identification ====================


@bp.post("/identify")
def identify_user():
    """Identify or create a user from context.
    
    Body (optional):
        name: User name
        voice_id: Voice fingerprint hash
        context_hints: Dict with timezone, language, etc.
    
    Returns:
        User profile with user_id
    """
    data = request.get_json(silent=True) or {}
    
    name = data.get("name")
    voice_id = data.get("voice_id")
    context_hints = data.get("context_hints", {})
    
    profiles = _get_profiles()
    user = profiles.identify_user(
        name=name,
        voice_id=voice_id,
        context_hints=context_hints,
    )
    
    _LOGGER.info("Identified user: %s (%s)", user.name, user.user_id)
    
    return jsonify({
        "status": "ok",
        "user": user.to_dict(),
    })


@bp.get("/users")
def list_users():
    """List all known users.
    
    Query params:
        active_only: true/false (default: false)
    
    Returns:
        List of user profiles
    """
    active_only = request.args.get("active_only", "false").lower() == "true"
    
    profiles = _get_profiles()
    users = profiles.get_all_users(active_only=active_only)
    
    return jsonify({
        "status": "ok",
        "users": [u.to_dict() for u in users],
        "count": len(users),
    })


@bp.get("/users/<user_id>")
def get_user(user_id: str):
    """Get a specific user profile."""
    profiles = _get_profiles()
    user = profiles.get_user(user_id)
    
    if not user:
        return jsonify({"error": "user_not_found"}), 404
    
    return jsonify({
        "status": "ok",
        "user": user.to_dict(),
    })


@bp.post("/users")
def create_user():
    """Create a new user profile.
    
    Body:
        name: User display name (required)
        voice_id: Optional voice fingerprint
        context_hints: Optional context dict
    
    Returns:
        Created user profile
    """
    data = request.get_json(silent=True) or {}
    
    name = data.get("name")
    if not name:
        return jsonify({"error": "name_required"}), 400
    
    voice_id = data.get("voice_id")
    context_hints = data.get("context_hints", {})
    
    profiles = _get_profiles()
    user = profiles.create_user(
        name=name,
        voice_id=voice_id,
        context_hints=context_hints,
    )
    
    _LOGGER.info("Created user: %s (%s)", name, user.user_id)
    
    return jsonify({
        "status": "created",
        "user": user.to_dict(),
    }), 201


@bp.put("/users/<user_id>")
def update_user(user_id: str):
    """Update a user profile.
    
    Body (all optional):
        name: New display name
        voice_id: New voice fingerprint
        context_hints: Additional context hints
    
    Returns:
        Updated user profile
    """
    data = request.get_json(silent=True) or {}
    
    profiles = _get_profiles()
    user = profiles.update_user(
        user_id=user_id,
        name=data.get("name"),
        voice_id=data.get("voice_id"),
        context_hints=data.get("context_hints"),
    )
    
    if not user:
        return jsonify({"error": "user_not_found"}), 404
    
    return jsonify({
        "status": "updated",
        "user": user.to_dict(),
    })


@bp.delete("/users/<user_id>")
def delete_user(user_id: str):
    """Delete a user profile and all preferences (GDPR).
    
    Returns:
        Status dict
    """
    profiles = _get_profiles()
    learner = _get_learner()
    
    # Delete preferences first
    learner.delete_all_user_preferences(user_id)
    
    # Then delete profile
    ok = profiles.delete_user(user_id)
    
    if not ok:
        return jsonify({"error": "user_not_found"}), 404
    
    _LOGGER.info("Deleted user and all data: %s", user_id)
    
    return jsonify({
        "status": "deleted",
        "user_id": user_id,
    })


# ==================== Preference CRUD ====================


@bp.get("/<user_id>")
def get_user_preferences(user_id: str):
    """Get all preferences for a user.
    
    Query params:
        min_confidence: Minimum confidence threshold (default: 0.3)
    
    Returns:
        Dict with user_id and list of preferences
    """
    min_conf = float(request.args.get("min_confidence", "0.3"))
    
    learner = _get_learner()
    prefs = learner.get_user_preferences(user_id, min_confidence=min_conf)
    
    # Verify user exists
    profiles = _get_profiles()
    user = profiles.get_user(user_id)
    if not user:
        return jsonify({"error": "user_not_found"}), 404
    
    return jsonify({
        "status": "ok",
        "user_id": user_id,
        "user_name": user.name,
        "preferences": [p.to_dict() for p in prefs],
        "count": len(prefs),
    })


@bp.get("/<user_id>/<key>")
def get_preference(user_id: str, key: str):
    """Get a specific preference for a user.
    
    Returns:
        Preference dict or 404 if not found
    """
    learner = _get_learner()
    pref = learner.get_preference(user_id, key)
    
    if not pref:
        return jsonify({"error": "preference_not_found"}), 404
    
    return jsonify({
        "status": "ok",
        "user_id": user_id,
        "preference": pref.to_dict(),
    })


@bp.post("/<user_id>")
def create_or_update_preference(user_id: str):
    """Create or update a preference for a user.
    
    Body:
        key: Preference key (required)
        value: Preference value (required)
        confidence: Optional confidence override (0-1)
    
    Returns:
        Created/updated preference
    """
    data = request.get_json(silent=True) or {}
    
    key = data.get("key")
    value = data.get("value")
    
    if not key or value is None:
        return jsonify({"error": "key_and_value_required"}), 400
    
    confidence = data.get("confidence")
    if confidence is not None:
        confidence = max(0.0, min(1.0, float(confidence)))
    
    learner = _get_learner()
    profiles = _get_profiles()
    
    # Verify user exists
    user = profiles.get_user(user_id)
    if not user:
        return jsonify({"error": "user_not_found"}), 404
    
    # Update preference
    pref = learner.update_preference(user_id, key, value, confidence)
    
    _LOGGER.info("Updated preference for %s: %s=%s", user_id, key, value)
    
    return jsonify({
        "status": "updated",
        "user_id": user_id,
        "preference": pref.to_dict(),
    })


@bp.put("/<user_id>/<key>")
def update_preference(user_id: str, key: str):
    """Update a specific preference.
    
    Body:
        value: New preference value (required)
        confidence: Optional confidence override
    
    Returns:
        Updated preference
    """
    data = request.get_json(silent=True) or {}
    
    value = data.get("value")
    if value is None:
        return jsonify({"error": "value_required"}), 400
    
    confidence = data.get("confidence")
    if confidence is not None:
        confidence = max(0.0, min(1.0, float(confidence)))
    
    learner = _get_learner()
    pref = learner.update_preference(user_id, key, value, confidence)
    
    if not pref:
        return jsonify({"error": "preference_not_found"}), 404
    
    return jsonify({
        "status": "updated",
        "user_id": user_id,
        "preference": pref.to_dict(),
    })


@bp.delete("/<user_id>/<key>")
def delete_preference(user_id: str, key: str):
    """Delete a specific preference.
    
    Returns:
        Status dict
    """
    learner = _get_learner()
    ok = learner.delete_preference(user_id, key)
    
    if not ok:
        return jsonify({"error": "preference_not_found"}), 404
    
    return jsonify({
        "status": "deleted",
        "user_id": user_id,
        "key": key,
    })


@bp.delete("/<user_id>")
def delete_all_preferences(user_id: str):
    """Delete all preferences for a user (GDPR).
    
    Returns:
        Status dict with count of deleted preferences
    """
    learner = _get_learner()
    count = learner.delete_all_user_preferences(user_id)
    
    return jsonify({
        "status": "deleted",
        "user_id": user_id,
        "deleted_count": count,
    })


# ==================== Learning from Conversation ====================


@bp.post("/<user_id>/learn")
def learn_from_message(user_id: str):
    """Learn preferences from a user message.
    
    Body:
        text: User message text (required)
        context: Optional context dict (topic, mood, etc.)
    
    Returns:
        List of learned preferences
    """
    data = request.get_json(silent=True) or {}
    
    text = data.get("text")
    if not text:
        return jsonify({"error": "text_required"}), 400
    
    context = data.get("context", {})
    
    learner = _get_learner()
    profiles = _get_profiles()
    
    # Verify user exists
    user = profiles.get_user(user_id)
    if not user:
        return jsonify({"error": "user_not_found"}), 404
    
    # Record interaction
    profiles.record_interaction(user_id)
    
    # Learn from message
    learned = learner.learn_from_message(user_id, text, context)
    
    _LOGGER.info("Learned %d preferences from message for %s", len(learned), user_id)
    
    return jsonify({
        "status": "ok",
        "user_id": user_id,
        "learned": [p.to_dict() for p in learned],
        "count": len(learned),
    })


# ==================== Export/Import (GDPR) ====================


@bp.get("/<user_id>/export")
def export_user_data(user_id: str):
    """Export all user data (GDPR).
    
    Returns:
        Complete user data export
    """
    profiles = _get_profiles()
    learner = _get_learner()
    
    # Get user profile
    user = profiles.get_user(user_id)
    if not user:
        return jsonify({"error": "user_not_found"}), 404
    
    # Get preferences
    prefs_export = learner.export_user_preferences(user_id)
    
    return jsonify({
        "status": "ok",
        "export": {
            "user_profile": user.to_dict(),
            "preferences": prefs_export,
            "exported_at": __import__("time").time(),
        },
    })


# ==================== Stats ====================


@bp.get("/stats")
def get_stats():
    """Get preference learning statistics."""
    learner = _get_learner()
    profiles = _get_profiles()
    
    pref_stats = learner.get_stats()
    profile_stats = profiles.get_stats()
    
    return jsonify({
        "status": "ok",
        "preference_learning": pref_stats,
        "user_profiles": profile_stats,
    })
