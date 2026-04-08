"""User Preference API endpoints for PilotSuite Core.

Provides endpoints for Multi-User Preference Learning (MUP-L).
Privacy-first: user IDs remain local and are never forwarded to external services.

Design Doc: docs/MUPL_DESIGN.md
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.storage.user_preferences import (
    UserPreferences,
    get_user_preference_store,
)

bp = Blueprint("user_preferences", __name__, url_prefix="/user")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401

_LOGGER = logging.getLogger(__name__)


def _get_ha_client():
    """Get Home Assistant client from app config."""
    cfg = current_app.config.get("COPILOT_CFG")
    if hasattr(cfg, "ha_client"):
        return cfg.ha_client
    return None


def _store():
    """Get the user preference store."""
    return get_user_preference_store()


@bp.get("/<user_id>/preferences")
def get_user_preferences(user_id: str):
    """Get all preferences for a user.
    
    Args:
        user_id: User ID (person entity_id)
        
    Returns:
        JSON with user_id and preferences dict
    """
    user = _store().get_user(user_id)
    if user:
        prefs = user.preferences
    else:
        prefs = {
            "light_brightness": {"default": 0.8, "by_zone": {}},
            "media_volume": {"default": 0.5, "by_zone": {}},
            "temperature": {"default": 21.0, "by_zone": {}},
            "mood_weights": {"comfort": 0.5, "frugality": 0.5, "joy": 0.5},
        }
    
    return jsonify({
        "user_id": user_id,
        "preferences": prefs,
    })


@bp.get("/<user_id>/zone/<zone_id>/preference")
def get_user_zone_preference(user_id: str, zone_id: str):
    """Get preference for a user in a specific zone.
    
    Args:
        user_id: User ID (person entity_id)
        zone_id: Zone ID (e.g., "living", "bedroom")
        
    Returns:
        JSON with user_id, zone_id, and preference
    """
    user = _store().get_user(user_id)
    
    if user:
        prefs = user.preferences
        mood = prefs.get("mood_weights", {"comfort": 0.5, "frugality": 0.5, "joy": 0.5})
    else:
        mood = {"comfort": 0.5, "frugality": 0.5, "joy": 0.5}
    
    return jsonify({
        "user_id": user_id,
        "zone_id": zone_id,
        "preference": {
            "mood_weights": mood,
        },
    })


@bp.post("/<user_id>/preference")
def update_user_preference(user_id: str):
    """Update a user's preference for a zone.
    
    Args:
        user_id: User ID (person entity_id)
        
    Body:
        zone_id: Zone ID (required)
        comfort_bias: Comfort bias (0.0-1.0, optional)
        frugality_bias: Frugality bias (0.0-1.0, optional)
        joy_bias: Joy bias (0.0-1.0, optional)
        
    Returns:
        Updated preference dict
    """
    data = request.get_json(silent=True) or {}
    
    zone_id = data.get("zone_id")
    if not zone_id:
        return jsonify({"error": "zone_id_required"}), 400
    
    # Build preference update
    prefs_update = {}
    mood = {}
    
    if "comfort_bias" in data:
        mood["comfort"] = max(0.0, min(1.0, float(data["comfort_bias"])))
    if "frugality_bias" in data:
        mood["frugality"] = max(0.0, min(1.0, float(data["frugality_bias"])))
    if "joy_bias" in data:
        mood["joy"] = max(0.0, min(1.0, float(data["joy_bias"])))
    
    if mood:
        prefs_update["mood_weights"] = mood
    
    # Update via store
    user = _store().update_user_preferences(user_id, prefs_update)
    
    _LOGGER.info("Updated preference for user %s in zone %s: %s", user_id, zone_id, mood)
    
    return jsonify({
        "user_id": user_id,
        "zone_id": zone_id,
        "preference": {"mood_weights": user.preferences.get("mood_weights", {})},
    })


@bp.get("/active")
def get_active_users():
    """Get list of currently active (home) users.
    
    Queries Home Assistant person entities to find users currently home.
    
    Returns:
        List of active user dicts with user_id and name
    """
    ha_client = _get_ha_client()
    active = []
    
    if ha_client:
        try:
            # Get all person entities
            states = ha_client.get_states()
            for state in states:
                if state.get("entity_id", "").startswith("person."):
                    if state.get("state") == "home":
                        user_id = state["entity_id"]
                        active.append({
                            "user_id": user_id,
                            "name": state.get("attributes", {}).get("friendly_name", user_id),
                        })
                        # Update store
                        _store().add_active_user(user_id)
        except Exception as e:
            _LOGGER.warning("Failed to get active users from HA: %s", e)
    
    return jsonify({
        "status": "ok",
        "users": active,
        "count": len(active),
    })


@bp.get("/all")
def get_all_users():
    """Get all known users with their preferences.
    
    Returns:
        Dict of user_id to user data
    """
    users = _store().get_all_users()
    
    return jsonify({
        "status": "ok",
        "users": {uid: u.to_dict() for uid, u in users.items()},
        "count": len(users),
    })


@bp.post("/<user_id>/priority")
def set_user_priority(user_id: str):
    """Set user priority for conflict resolution.
    
    Args:
        user_id: User ID
        
    Body:
        priority: Priority value (0.0-1.0, higher = more important)
        
    Returns:
        Updated user data
    """
    data = request.get_json(silent=True) or {}
    
    priority = data.get("priority")
    if priority is None:
        return jsonify({"error": "priority_required"}), 400
    
    priority = max(0.0, min(1.0, float(priority)))
    
    ok = _store().update_user_priority(user_id, priority)
    
    if not ok:
        return jsonify({"error": "user_not_found"}), 404
    
    _LOGGER.info("Set priority %.2f for user %s", priority, user_id)
    
    return jsonify({
        "user_id": user_id,
        "priority": priority,
    })


@bp.delete("/<user_id>")
def delete_user_data(user_id: str):
    """Delete all data for a user (privacy/GDPR).
    
    Args:
        user_id: User to delete
        
    Returns:
        Status dict
    """
    ok = _store().delete_user(user_id)
    
    if not ok:
        return jsonify({"error": "user_not_found"}), 404
    
    _LOGGER.info("Deleted all data for user: %s", user_id)
    
    return jsonify({"status": "deleted", "user_id": user_id})


@bp.get("/<user_id>/export")
def export_user_data(user_id: str):
    """Export all data for a user (privacy/GDPR).
    
    Args:
        user_id: User to export
        
    Returns:
        User data dict
    """
    data = _store().export_user_data(user_id)
    
    if not data:
        return jsonify({"error": "user_not_found"}), 404
    
    return jsonify(data)


# ==================== Aggregated Mood ====================


@bp.get("/mood/aggregated")
def get_aggregated_mood():
    """Get aggregated mood for multiple users.

    Query params:
        users: Comma-separated list of user IDs (optional, defaults to active users)

    Returns:
        Aggregated mood dict with comfort, frugality, joy
    """
    users_param = request.args.get("users")

    if users_param:
        user_ids = [u.strip() for u in users_param.split(",") if u.strip()]
    else:
        user_ids = _store().get_active_users()

    mood = _store().get_aggregated_mood(user_ids)

    return jsonify({
        "status": "ok",
        "mood": mood,
        "user_count": len(user_ids),
    })


# ==================== Role Inference ====================


def _mupl():
    """Get the MUPL module (lazy-loaded)."""
    cfg = current_app.config.get("COPILOT_CFG")
    mupl = getattr(cfg, "mupl", None)
    if mupl is None:
        from copilot_core.neurons.mupl import create_mupl_module
        mupl = create_mupl_module()
        if cfg:
            cfg.mupl = mupl
    return mupl


@bp.get("/<user_id>/role")
def get_user_role(user_id: str):
    """Get inferred role for a user.

    Returns role, confidence, device count, and automation count.
    """
    mupl = _mupl()
    profile = mupl.get_user_profile(user_id)

    if not profile:
        return jsonify({
            "user_id": user_id,
            "role": "unknown",
            "confidence": 0.0,
            "device_count": 0,
            "automation_count": 0,
        })

    return jsonify({
        "user_id": user_id,
        "role": profile.role.value,
        "confidence": profile.confidence,
        "device_count": profile.device_count,
        "automation_count": profile.automation_count,
    })


@bp.get("/roles")
def get_all_roles():
    """Get inferred roles for all known users."""
    mupl = _mupl()
    profiles = mupl.get_all_profiles()

    result = {}
    for uid, profile in profiles.items():
        if profile:
            result[uid] = {
                "role": profile.role.value,
                "confidence": profile.confidence,
                "device_count": profile.device_count,
            }

    return jsonify({"status": "ok", "roles": result, "count": len(result)})


@bp.post("/<user_id>/device/<device_id>")
def register_device_usage(user_id: str, device_id: str):
    """Register that a user controlled a device.

    Used for role inference and device affinity tracking.
    """
    mupl = _mupl()
    mupl.register_device_control(user_id, device_id)

    # Also update device affinity in the preference store
    _store().update_device_affinity(user_id, device_id)

    _LOGGER.debug("Registered device control: %s → %s", user_id, device_id)
    return jsonify({"status": "ok"})


@bp.get("/<user_id>/access/<device_id>")
def check_device_access(user_id: str, device_id: str):
    """Check if user has access to a device (RBAC)."""
    mupl = _mupl()
    allowed = mupl.check_access(user_id, device_id)

    return jsonify({
        "user_id": user_id,
        "device_id": device_id,
        "allowed": allowed,
    })


# ==================== Delegation ====================


@bp.post("/<user_id>/delegate")
def delegate_device(user_id: str):
    """Delegate device access from one user to another.

    Body:
        target_user_id: User to receive access
        device_id: Device to delegate
        expires_hours: Optional expiry in hours (0 = permanent)

    Only Device Managers can delegate.
    """
    import time as _time

    data = request.get_json(silent=True) or {}
    target = data.get("target_user_id")
    device_id = data.get("device_id")

    if not target or not device_id:
        return jsonify({"error": "target_user_id and device_id required"}), 400

    mupl = _mupl()

    # Check caller has permission to delegate
    caller_profile = mupl.get_user_profile(user_id)
    if not caller_profile or caller_profile.role.value != "device_manager":
        return jsonify({"error": "only_device_managers_can_delegate"}), 403

    # Register device for target user
    mupl.register_device_control(target, device_id)

    # Track delegation in store
    expires_hours = float(data.get("expires_hours", 0))
    expires_at = _time.time() + expires_hours * 3600 if expires_hours > 0 else None

    store = _store()
    delegations = store._load_extra("delegations") or []
    delegations.append({
        "from": user_id,
        "to": target,
        "device_id": device_id,
        "created_at": _time.time(),
        "expires_at": expires_at,
    })
    store._save_extra("delegations", delegations)

    _LOGGER.info("Delegation: %s → %s for device %s", user_id, target, device_id)

    return jsonify({
        "status": "delegated",
        "from": user_id,
        "to": target,
        "device_id": device_id,
        "expires_at": expires_at,
    })


@bp.delete("/<user_id>/delegate")
def revoke_delegation(user_id: str):
    """Revoke a device delegation.

    Body:
        target_user_id: User to revoke from
        device_id: Device to revoke
    """
    data = request.get_json(silent=True) or {}
    target = data.get("target_user_id")
    device_id = data.get("device_id")

    if not target or not device_id:
        return jsonify({"error": "target_user_id and device_id required"}), 400

    store = _store()
    delegations = store._load_extra("delegations") or []
    before = len(delegations)
    delegations = [
        d for d in delegations
        if not (d["from"] == user_id and d["to"] == target and d["device_id"] == device_id)
    ]
    store._save_extra("delegations", delegations)

    removed = before - len(delegations)
    _LOGGER.info("Revoked %d delegation(s): %s → %s for %s", removed, user_id, target, device_id)

    return jsonify({"status": "revoked", "removed": removed})


@bp.get("/delegations")
def list_delegations():
    """List all active delegations."""
    import time as _time

    store = _store()
    delegations = store._load_extra("delegations") or []

    # Filter expired
    now = _time.time()
    active = [d for d in delegations if not d.get("expires_at") or d["expires_at"] > now]

    # Clean up expired
    if len(active) != len(delegations):
        store._save_extra("delegations", active)

    return jsonify({"status": "ok", "delegations": active, "count": len(active)})


# ==================== Conflict Resolution ====================


@bp.post("/conflicts/evaluate")
def evaluate_conflicts():
    """Evaluate preference conflicts between active users.

    Body (optional):
        user_ids: list of user IDs (default: all known users)
        strategy: "weighted" | "compromise" | "override"
        override_user: user_id for override strategy

    Returns:
        Conflict state with details and resolved mood.
    """
    data = request.get_json(silent=True) or {}
    user_ids = data.get("user_ids")
    strategy = data.get("strategy", "weighted")
    override_user = data.get("override_user")

    store = _store()
    users = store.get_all_users()

    if user_ids:
        users = {uid: u for uid, u in users.items() if uid in user_ids}

    if len(users) < 2:
        return jsonify({
            "active": False,
            "conflict_count": 0,
            "users_involved": list(users.keys()),
            "resolution": strategy,
            "resolved_mood": {"comfort": 0.5, "frugality": 0.5, "joy": 0.5},
            "details": [],
        })

    # Extract per-user moods and priorities
    user_moods = {}
    user_priorities = {}
    for uid, u in users.items():
        user_moods[uid] = u.preferences.get(
            "mood_weights", {"comfort": 0.5, "frugality": 0.5, "joy": 0.5}
        )
        user_priorities[uid] = u.priority

    # Detect conflicts (threshold: 0.3 divergence on any axis)
    threshold = 0.3
    conflicts = []
    uids = list(user_moods.keys())
    for i, ua in enumerate(uids):
        for ub in uids[i + 1:]:
            for axis in ("comfort", "frugality", "joy"):
                va = user_moods[ua].get(axis, 0.5)
                vb = user_moods[ub].get(axis, 0.5)
                div = abs(va - vb)
                if div >= threshold:
                    conflicts.append({
                        "axis": axis,
                        "user_a": ua,
                        "user_b": ub,
                        "value_a": round(va, 2),
                        "value_b": round(vb, 2),
                        "divergence": round(div, 2),
                    })

    # Resolve
    if strategy == "override" and override_user and override_user in user_moods:
        resolved = dict(user_moods[override_user])
    elif strategy == "compromise":
        resolved = {"comfort": 0.0, "frugality": 0.0, "joy": 0.0}
        for um in user_moods.values():
            for k in resolved:
                resolved[k] += um.get(k, 0.5)
        n = len(user_moods)
        resolved = {k: round(v / n, 3) for k, v in resolved.items()}
    else:
        resolved = store.get_aggregated_mood(uids)

    return jsonify({
        "active": len(conflicts) > 0,
        "conflict_count": len(conflicts),
        "users_involved": uids,
        "resolution": strategy,
        "resolved_mood": resolved,
        "details": conflicts,
    })