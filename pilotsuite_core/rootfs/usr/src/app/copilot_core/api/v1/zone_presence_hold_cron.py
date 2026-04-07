"""Zone Presence Hold Cron API for Slice 44.

Exposes hold expiration cron service for manual triggers and scheduler integration.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from typing import Any, Dict
import logging

from copilot_core.core.zone_presence_hold_cron import (
    get_hold_cron_service,
    run_hold_expiration_check,
    HoldExpirationCronSummary,
)

logger = logging.getLogger(__name__)

blueprint = Blueprint("zone_presence_hold_cron", __name__, url_prefix="/api/v1/presence/holds/cron")


@blueprint.route("/run", methods=["POST"])
def run_expiration_check() -> tuple[Dict[str, Any], int]:
    """Manually trigger a hold expiration check.
    
    This endpoint is intended for:
    - Manual testing/debugging
    - Scheduler/cron job integration
    - Immediate processing after hold creation
    
    Returns:
        HoldExpirationCronSummary with all actions taken.
    """
    try:
        summary = run_hold_expiration_check()
        return jsonify(summary.to_dict()), 200
    except Exception as e:
        logger.exception("Hold expiration check failed")
        return jsonify({
            "error": "Hold expiration check failed",
            "details": str(e),
        }), 500


@blueprint.route("/status", methods=["GET"])
def get_cron_status() -> tuple[Dict[str, Any], int]:
    """Get the last cron run status.
    
    Returns:
        Last HoldExpirationCronSummary or empty status if never run.
    """
    try:
        service = get_hold_cron_service()
        last_summary = service.get_last_summary()
        
        if last_summary:
            return jsonify(last_summary.to_dict()), 200
        else:
            return jsonify({
                "status": "never_run",
                "cron_revision": service.get_cron_revision(),
            }), 200
    except Exception as e:
        logger.exception("Failed to get cron status")
        return jsonify({
            "error": "Failed to get cron status",
            "details": str(e),
        }), 500


@blueprint.route("/revision", methods=["GET"])
def get_cron_revision() -> tuple[Dict[str, Any], int]:
    """Get current cron revision for delta polling.
    
    Returns:
        Current cron revision number.
    """
    try:
        service = get_hold_cron_service()
        return jsonify({
            "cron_revision": service.get_cron_revision(),
            "last_run_at": service._last_run_at,
        }), 200
    except Exception as e:
        logger.exception("Failed to get cron revision")
        return jsonify({
            "error": "Failed to get cron revision",
            "details": str(e),
        }), 500


@blueprint.route("/config", methods=["GET"])
def get_cron_config() -> tuple[Dict[str, Any], int]:
    """Get cron service configuration.
    
    Returns:
        Current configuration settings.
    """
    try:
        service = get_hold_cron_service()
        return jsonify({
            "expiring_soon_window_minutes": service.expiring_soon_window_minutes,
            "auto_release_on_expire": service.auto_release_on_expire,
        }), 200
    except Exception as e:
        logger.exception("Failed to get cron config")
        return jsonify({
            "error": "Failed to get cron config",
            "details": str(e),
        }), 500


@blueprint.route("/config", methods=["PUT"])
def update_cron_config() -> tuple[Dict[str, Any], int]:
    """Update cron service configuration.
    
    Body:
        {
            "expiring_soon_window_minutes": 15,  # Optional
            "auto_release_on_expire": true       # Optional
        }
    
    Returns:
        Updated configuration.
    """
    try:
        service = get_hold_cron_service()
        body = request.get_json() or {}
        
        if "expiring_soon_window_minutes" in body:
            service.expiring_soon_window_minutes = int(body["expiring_soon_window_minutes"])
        
        if "auto_release_on_expire" in body:
            service.auto_release_on_expire = bool(body["auto_release_on_expire"])
        
        return jsonify({
            "expiring_soon_window_minutes": service.expiring_soon_window_minutes,
            "auto_release_on_expire": service.auto_release_on_expire,
        }), 200
    except Exception as e:
        logger.exception("Failed to update cron config")
        return jsonify({
            "error": "Failed to update cron config",
            "details": str(e),
        }), 500
