"""
User Profile and Preferences API v1 for PilotSuite Core.

Provides REST endpoints for managing user profiles and notification preferences.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
from typing import Optional

from ...users.contracts import (
    UserProfileV1,
    NotificationPreferencesV1,
    ChannelPreferencesV1,
    NotificationChannel,
    NotificationCategory,
    NotificationPriority,
    DeliveryMode,
)
from ...users.store import UserStore


def create_users_blueprint(user_store: UserStore):
    """Create Flask blueprint for users API."""
    bp = Blueprint("users", __name__, url_prefix="/api/v1/users")
    
    @bp.route("/profile", methods=["GET"])
    def get_profile():
        """
        Get current user profile.
        
        Query params:
        - user_id: user ID (defaults to "default" if not provided)
        """
        user_id = request.args.get("user_id", "default")
        
        profile = user_store.get_profile(user_id)
        
        if not profile:
            return jsonify({"error": "User profile not found"}), 404
        
        return jsonify(profile.to_dict())
    
    @bp.route("/profile", methods=["PUT"])
    def update_profile():
        """
        Update or create user profile.
        
        Body:
        - name: optional display name
        - email: optional email address
        - timezone: timezone (default: Europe/Berlin)
        - language: language code (default: de)
        - metadata: optional metadata dict
        """
        user_id = request.args.get("user_id", "default")
        data = request.get_json() or {}
        
        profile = user_store.get_profile(user_id)
        
        if profile:
            # Update existing
            profile.name = data.get("name", profile.name)
            profile.email = data.get("email", profile.email)
            profile.timezone = data.get("timezone", profile.timezone)
            profile.language = data.get("language", profile.language)
            profile.metadata = {**profile.metadata, **data.get("metadata", {})}
        else:
            # Create new
            profile = UserProfileV1(
                user_id=user_id,
                name=data.get("name"),
                email=data.get("email"),
                timezone=data.get("timezone", "Europe/Berlin"),
                language=data.get("language", "de"),
                created_at=datetime.now(timezone.utc),
                metadata=data.get("metadata", {}),
            )
        
        updated = user_store.upsert_profile(profile)
        
        return jsonify(updated.to_dict())
    
    @bp.route("/preferences", methods=["GET"])
    def get_preferences():
        """
        Get current user notification preferences.
        
        Query params:
        - user_id: user ID (defaults to "default")
        """
        user_id = request.args.get("user_id", "default")
        
        prefs = user_store.get_preferences(user_id)
        
        if not prefs:
            return jsonify({"error": "User preferences not found"}), 404
        
        return jsonify(prefs.to_dict())
    
    @bp.route("/preferences", methods=["PUT"])
    def update_preferences():
        """
        Update or create notification preferences.
        
        Body:
        - global_enabled: bool
        - global_quiet_hours_start: str (HH:MM)
        - global_quiet_hours_end: str (HH:MM)
        - do_not_disturb: bool
        - do_not_disturb_until: ISO timestamp
        - default_channel: str (telegram|push|email|whatsapp|slack|webhook)
        - digest_schedule: str (cron expression)
        - digest_enabled: bool
        - channel_preferences: dict of channel settings
        """
        user_id = request.args.get("user_id", "default")
        data = request.get_json() or {}
        
        prefs = user_store.get_preferences(user_id)
        
        if prefs:
            # Update existing
            prefs.global_enabled = data.get("global_enabled", prefs.global_enabled)
            prefs.global_quiet_hours_start = data.get("global_quiet_hours_start", prefs.global_quiet_hours_start)
            prefs.global_quiet_hours_end = data.get("global_quiet_hours_end", prefs.global_quiet_hours_end)
            prefs.do_not_disturb = data.get("do_not_disturb", prefs.do_not_disturb)
            prefs.default_channel = NotificationChannel(data.get("default_channel", prefs.default_channel.value))
            prefs.digest_schedule = data.get("digest_schedule", prefs.digest_schedule)
            prefs.digest_enabled = data.get("digest_enabled", prefs.digest_enabled)
            
            if "do_not_disturb_until" in data:
                prefs.do_not_disturb_until = (
                    datetime.fromisoformat(data["do_not_disturb_until"])
                    if data["do_not_disturb_until"]
                    else None
                )
            
            # Update channel preferences
            if "channel_preferences" in data:
                for ch_key, ch_data in data["channel_preferences"].items():
                    channel = NotificationChannel(ch_key)
                    if channel not in prefs.channel_preferences:
                        prefs.channel_preferences[ch_key] = ChannelPreferencesV1(channel=channel)
                    
                    ch_prefs = prefs.channel_preferences[ch_key]
                    ch_prefs.enabled = ch_data.get("enabled", ch_prefs.enabled)
                    ch_prefs.delivery_mode = DeliveryMode(ch_data.get("delivery_mode", ch_prefs.delivery_mode.value))
                    ch_prefs.min_priority = NotificationPriority(ch_data.get("min_priority", ch_prefs.min_priority.value))
        else:
            # Create new with defaults
            channel_prefs = {}
            for ch_data in data.get("channel_preferences", {}).values():
                channel = NotificationChannel(ch_data.get("channel", "telegram"))
                channel_prefs[channel.value] = ChannelPreferencesV1(
                    channel=channel,
                    enabled=ch_data.get("enabled", True),
                    delivery_mode=DeliveryMode(ch_data.get("delivery_mode", "immediate")),
                    min_priority=NotificationPriority(ch_data.get("min_priority", "low")),
                )
            
            prefs = NotificationPreferencesV1(
                user_id=user_id,
                global_enabled=data.get("global_enabled", True),
                global_quiet_hours_start=data.get("global_quiet_hours_start"),
                global_quiet_hours_end=data.get("global_quiet_hours_end"),
                do_not_disturb=data.get("do_not_disturb", False),
                do_not_disturb_until=(
                    datetime.fromisoformat(data["do_not_disturb_until"])
                    if data.get("do_not_disturb_until")
                    else None
                ),
                default_channel=NotificationChannel(data.get("default_channel", "telegram")),
                channel_preferences=channel_prefs,
                digest_schedule=data.get("digest_schedule"),
                digest_enabled=data.get("digest_enabled", False),
            )
        
        updated = user_store.upsert_preferences(prefs)
        
        return jsonify(updated.to_dict())
    
    @bp.route("/settings", methods=["GET"])
    def get_settings():
        """
        Get combined user settings (profile + preferences).
        
        Query params:
        - user_id: user ID (defaults to "default")
        """
        user_id = request.args.get("user_id", "default")
        
        settings = user_store.get_settings(user_id)
        
        if not settings:
            return jsonify({"error": "User settings not found"}), 404
        
        return jsonify(settings.to_dict())
    
    @bp.route("/preferences/dnd", methods=["PUT"])
    def update_dnd():
        """
        Update do-not-disturb status.
        
        Body:
        - do_not_disturb: bool (required)
        - until: ISO timestamp (optional)
        """
        user_id = request.args.get("user_id", "default")
        data = request.get_json() or {}
        
        if "do_not_disturb" not in data:
            return jsonify({"error": "do_not_disturb is required"}), 400
        
        dnd = data["do_not_disturb"]
        until = None
        if "until" in data and data["until"]:
            until = datetime.fromisoformat(data["until"])
        
        updated = user_store.update_preferences_dnd(user_id, dnd, until)
        
        if not updated:
            return jsonify({"error": "User preferences not found"}), 404
        
        return jsonify(updated.to_dict())
    
    @bp.route("/preferences/channel/<channel>", methods=["PUT"])
    def update_channel(channel: str):
        """
        Update a specific channel preference.
        
        Path params:
        - channel: channel name (telegram|push|email|whatsapp|slack|webhook)
        
        Body:
        - enabled: bool
        - delivery_mode: str (immediate|batched|digest_only|silent)
        - min_priority: str (critical|high|normal|low)
        """
        user_id = request.args.get("user_id", "default")
        data = request.get_json() or {}
        
        try:
            channel_enum = NotificationChannel(channel)
        except ValueError:
            return jsonify({"error": f"Invalid channel: {channel}"}), 400
        
        enabled = data.get("enabled")
        delivery_mode = None
        min_priority = None
        
        if "delivery_mode" in data:
            try:
                delivery_mode = DeliveryMode(data["delivery_mode"])
            except ValueError:
                return jsonify({"error": f"Invalid delivery_mode: {data['delivery_mode']}"}), 400
        
        if "min_priority" in data:
            try:
                min_priority = NotificationPriority(data["min_priority"])
            except ValueError:
                return jsonify({"error": f"Invalid min_priority: {data['min_priority']}"}), 400
        
        updated = user_store.update_channel_preference(
            user_id,
            channel_enum,
            enabled=enabled,
            delivery_mode=delivery_mode,
            min_priority=min_priority,
        )
        
        if not updated:
            return jsonify({"error": "User preferences not found"}), 404
        
        return jsonify(updated.to_dict())
    
    @bp.route("", methods=["DELETE"])
    def delete_user():
        """
        Delete user and all associated data.
        
        Query params:
        - user_id: user ID (defaults to "default")
        """
        user_id = request.args.get("user_id", "default")
        
        deleted = user_store.delete_user(user_id)
        
        if not deleted:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify({"deleted": True, "user_id": user_id})
    
    @bp.route("/channels", methods=["GET"])
    def list_channels():
        """List all available notification channels."""
        return jsonify({
            "channels": [c.value for c in NotificationChannel],
        })
    
    @bp.route("/categories", methods=["GET"])
    def list_categories():
        """List all available notification categories."""
        return jsonify({
            "categories": [c.value for c in NotificationCategory],
        })
    
    @bp.route("/priorities", methods=["GET"])
    def list_priorities():
        """List all available notification priorities."""
        return jsonify({
            "priorities": [p.value for p in NotificationPriority],
        })
    
    @bp.route("/delivery-modes", methods=["GET"])
    def list_delivery_modes():
        """List all available delivery modes."""
        return jsonify({
            "delivery_modes": [m.value for m in DeliveryMode],
        })
    
    return bp


# Default blueprint instance for registry (lazy init with default db_path)
_bp: Optional[Blueprint] = None

def _get_bp() -> Blueprint:
    """Lazy-init the users blueprint with default UserStore."""
    global _bp
    if _bp is None:
        from ...users.store import UserStore
        _bp = create_users_blueprint(UserStore(db_path="data/users.db"))
    return _bp

bp = _get_bp()


__all__ = ["bp", "create_users_blueprint"]


# ── SLICE 142: Users API Expansion ─────────────────────────────────

@bp.get("/<user_id>/preferences")
def user_preferences(user_id):
    """Get user preferences.
    
    Returns all stored preferences for the user.
    """
    from copilot_core.users.store import get_user_store
    
    try:
        store = get_user_store()
        prefs = store.get_preferences(user_id=user_id)
    except Exception as e:
        _LOGGER.warning("Failed to get user preferences: %s", e)
        prefs = {}
    
    return jsonify({
        "ok": True,
        "user_id": user_id,
        "preferences": prefs,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.put("/<user_id>/preferences")
def update_user_preferences(user_id):
    """Update user preferences.
    
    Requires admin token.
    
    Body:
    - preferences: Dict of preference key-value pairs
    """
    auth_error = _require_admin_mutation("UPDATE_USER_PREFS", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    prefs = data.get("preferences", {})
    
    from copilot_core.users.store import get_user_store
    
    try:
        store = get_user_store()
        store.update_preferences(user_id=user_id, preferences=prefs)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to update user preferences: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "user_id": user_id,
        "preferences": prefs
    })


@bp.get("/<user_id>/activity")
def user_activity(user_id):
    """Get user activity history.
    
    Query params:
    - limit: Max entries (default 20)
    - days: Days to look back (default 7)
    """
    from copilot_core.users.store import get_user_store
    
    try:
        limit = int(request.args.get("limit", "20"))
    except (ValueError, TypeError):
        limit = 20
    
    try:
        days = int(request.args.get("days", "7"))
    except (ValueError, TypeError):
        days = 7
    
    limit = max(1, min(limit, 100))
    days = max(1, min(days, 90))
    
    try:
        store = get_user_store()
        activity = store.get_activity(user_id=user_id, limit=limit, days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get user activity: %s", e)
        activity = []
    
    return jsonify({
        "ok": True,
        "user_id": user_id,
        "activity": activity,
        "count": len(activity),
        "limit": limit,
        "days": days
    })


@bp.get("/activity/analytics")
def users_activity_analytics():
    """Get aggregated user activity analytics.
    
    Query params:
    - days: Days to analyze (default 30)
    """
    from copilot_core.users.store import get_user_store
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    days = max(1, min(days, 365))
    
    try:
        store = get_user_store()
        analytics = store.get_activity_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get activity analytics: %s", e)
        analytics = {
            "total_users": 0,
            "active_users": 0,
            "total_actions": 0,
            "avg_actions_per_user": 0.0
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
