"""Zone Presence Hold / Release API for Slice 39.

Enables deterministic zone presence hold/release so presence recognition
does not flicker on short absence windows. Provides canonical hold state
tracking with expiration, reason tracking, and zone-scoped hold visibility.
"""
from __future__ import annotations

from typing import Any
from flask import Blueprint, jsonify, request

from copilot_core.core.zone_presence_hold import (
    get_zone_presence_hold_store,
    ZoneHoldState,
)


zone_presence_hold_bp = Blueprint("zone_presence_hold", __name__, url_prefix="/presence/zones")


@zone_presence_hold_bp.route("/<zone_id>/hold", methods=["POST"])
def set_zone_hold(zone_id: str) -> tuple[Any, int]:
    """Set zone presence hold state.
    
    Request body:
    {
        "hold_state": "auto" | "force_on" | "force_off",
        "reason": "manual" (optional),
        "duration_seconds": 3600 (optional, auto-expire)
    }
    
    Response: ZonePresenceHoldV1
    """
    data = request.get_json() or {}
    
    hold_state_str = data.get("hold_state", "auto")
    reason = data.get("reason", "manual")
    duration_seconds = data.get("duration_seconds")
    
    if hold_state_str not in {"auto", "force_on", "force_off"}:
        return jsonify({
            "error": "hold_state must be auto, force_on, or force_off",
        }), 400
    
    hold_state = ZoneHoldState(hold_state_str)
    
    store = get_zone_presence_hold_store()
    hold = store.set_hold(
        zone_id=zone_id,
        hold_state=hold_state,
        reason=reason,
        duration_seconds=duration_seconds,
    )
    
    return jsonify(hold.to_dict()), 200


@zone_presence_hold_bp.route("/<zone_id>/hold", methods=["DELETE"])
def release_zone_hold(zone_id: str) -> tuple[Any, int]:
    """Release zone presence hold (reset to auto).
    
    Query params:
    - reason: string (optional, default "manual_release")
    
    Response: { "released": true, "zone_id": "..." } or 404
    """
    reason = request.args.get("reason", "manual_release")
    
    store = get_zone_presence_hold_store()
    released = store.release_hold(zone_id=zone_id, reason=reason)
    
    if not released:
        return jsonify({
            "error": "no active hold found for zone",
            "zone_id": zone_id,
        }), 404
    
    return jsonify({
        "released": True,
        "zone_id": zone_id,
        "reason": reason,
    }), 200


@zone_presence_hold_bp.route("/<zone_id>/hold", methods=["GET"])
def get_zone_hold(zone_id: str) -> tuple[Any, int]:
    """Get current hold for a zone.
    
    Response: ZonePresenceHoldV1 or 404 if no hold exists
    """
    store = get_zone_presence_hold_store()
    hold = store.get_hold_by_zone(zone_id)
    
    if not hold:
        return jsonify({
            "error": "no hold found for zone",
            "zone_id": zone_id,
        }), 404
    
    return jsonify(hold.to_dict()), 200


@zone_presence_hold_bp.route("/<zone_id>/state", methods=["GET"])
def get_zone_hold_state(zone_id: str) -> tuple[Any, int]:
    """Get effective hold state for a zone (AUTO if no active hold).
    
    Response: { "zone_id": "...", "hold_state": "auto"|"force_on"|"force_off", "is_enforced": bool }
    """
    store = get_zone_presence_hold_store()
    hold_state = store.get_active_hold_state(zone_id)
    hold = store.get_hold_by_zone(zone_id)
    
    is_enforced = hold.should_enforce() if hold else False
    
    return jsonify({
        "zone_id": zone_id,
        "hold_state": hold_state.value,
        "is_enforced": is_enforced,
        "hold": hold.to_dict() if hold else None,
    }), 200


@zone_presence_hold_bp.route("/holds", methods=["GET"])
def get_holds() -> tuple[Any, int]:
    """Get aggregated hold summary.
    
    Query params:
    - since_revision: int (optional)
    - recent_limit: int (optional, default 10)
    - zone_id: string (optional)
    - active_only: bool (optional, default false)
    
    Response: ZonePresenceHoldSummaryV1
    """
    since_revision: int | None = None
    if request.args.get("since_revision"):
        try:
            since_revision = int(request.args.get("since_revision"))
        except (ValueError, TypeError):
            pass
    
    recent_limit = 10
    if request.args.get("recent_limit"):
        try:
            recent_limit = int(request.args.get("recent_limit"))
        except (ValueError, TypeError):
            pass
    
    zone_id = request.args.get("zone_id")
    active_only = request.args.get("active_only", "false").lower() == "true"
    
    store = get_zone_presence_hold_store()
    
    if active_only:
        holds = store.get_all_holds(limit=recent_limit, zone_id=zone_id, active_only=True)
        summary = store.get_hold_summary(
            since_revision=since_revision,
            recent_limit=recent_limit,
            zone_id=zone_id,
        )
        return jsonify({
            **summary.to_dict(),
            "holds": [h.to_dict() for h in holds],
        }), 200
    
    summary = store.get_hold_summary(
        since_revision=since_revision,
        recent_limit=recent_limit,
        zone_id=zone_id,
    )
    
    return jsonify(summary.to_dict()), 200


@zone_presence_hold_bp.route("/holds/<hold_id>", methods=["GET"])
def get_hold(hold_id: str) -> tuple[Any, int]:
    """Get a single hold by ID.
    
    Response: ZonePresenceHoldV1 or 404
    """
    store = get_zone_presence_hold_store()
    hold = store.get_hold(hold_id)
    
    if not hold:
        return jsonify({
            "error": "hold not found",
            "hold_id": hold_id,
        }), 404
    
    return jsonify(hold.to_dict()), 200


def create_blueprint() -> Blueprint:
    """Create and return the zone presence hold blueprint."""
    return zone_presence_hold_bp
