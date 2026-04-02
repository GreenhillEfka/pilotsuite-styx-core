"""Zone Presence Hold Scheduler API for Slice 45.

Exposes scheduler integration controls for hold expiration checking.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from typing import Any, Dict
import logging

from copilot_core.core.zone_presence_hold_scheduler import (
    get_hold_scheduler_integration,
    attach_hold_scheduler_to_engine,
)

logger = logging.getLogger(__name__)

blueprint = Blueprint("zone_presence_hold_scheduler", __name__, url_prefix="/api/v1/presence/holds/scheduler")


@blueprint.route("/status", methods=["GET"])
def get_scheduler_status() -> tuple[Dict[str, Any], int]:
    """Get the scheduler integration status.
    
    Returns:
        Current scheduler job status including interval, enabled state, and next run.
    """
    try:
        integration = get_hold_scheduler_integration()
        status = integration.get_job_status()
        return jsonify(status), 200
    except Exception as e:
        logger.exception("Failed to get scheduler status")
        return jsonify({
            "error": "Failed to get scheduler status",
            "details": str(e),
        }), 500


@blueprint.route("/config", methods=["GET"])
def get_scheduler_config() -> tuple[Dict[str, Any], int]:
    """Get scheduler configuration.
    
    Returns:
        Current configuration settings (interval, enabled).
    """
    try:
        integration = get_hold_scheduler_integration()
        return jsonify({
            "interval_seconds": integration.get_interval(),
            "enabled": integration.is_enabled(),
        }), 200
    except Exception as e:
        logger.exception("Failed to get scheduler config")
        return jsonify({
            "error": "Failed to get scheduler config",
            "details": str(e),
        }), 500


@blueprint.route("/config", methods=["PUT"])
def update_scheduler_config() -> tuple[Dict[str, Any], int]:
    """Update scheduler configuration.
    
    Body:
        {
            "interval_seconds": 300,  # Optional, min 30
            "enabled": true           # Optional
        }
    
    Returns:
        Updated configuration.
    """
    try:
        integration = get_hold_scheduler_integration()
        body = request.get_json() or {}
        
        if "interval_seconds" in body:
            integration.set_interval(int(body["interval_seconds"]))
        
        if "enabled" in body:
            if body["enabled"]:
                integration.enable()
            else:
                integration.disable()
        
        return jsonify({
            "interval_seconds": integration.get_interval(),
            "enabled": integration.is_enabled(),
        }), 200
    except Exception as e:
        logger.exception("Failed to update scheduler config")
        return jsonify({
            "error": "Failed to update scheduler config",
            "details": str(e),
        }), 500


@blueprint.route("/run", methods=["POST"])
def run_expiration_check() -> tuple[Dict[str, Any], int]:
    """Manually trigger a hold expiration check.
    
    This bypasses the scheduler and runs immediately.
    
    Returns:
        Result of the check.
    """
    try:
        integration = get_hold_scheduler_integration()
        result = integration.run_now()
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    except Exception as e:
        logger.exception("Manual hold expiration check failed")
        return jsonify({
            "error": "Manual hold expiration check failed",
            "details": str(e),
        }), 500


@blueprint.route("/enable", methods=["POST"])
def enable_scheduler() -> tuple[Dict[str, Any], int]:
    """Enable the scheduler job.
    
    Returns:
        Updated status.
    """
    try:
        integration = get_hold_scheduler_integration()
        integration.enable()
        return jsonify({
            "enabled": True,
            "status": integration.get_job_status(),
        }), 200
    except Exception as e:
        logger.exception("Failed to enable scheduler")
        return jsonify({
            "error": "Failed to enable scheduler",
            "details": str(e),
        }), 500


@blueprint.route("/disable", methods=["POST"])
def disable_scheduler() -> tuple[Dict[str, Any], int]:
    """Disable the scheduler job.
    
    Returns:
        Updated status.
    """
    try:
        integration = get_hold_scheduler_integration()
        integration.disable()
        return jsonify({
            "enabled": False,
            "status": integration.get_job_status(),
        }), 200
    except Exception as e:
        logger.exception("Failed to disable scheduler")
        return jsonify({
            "error": "Failed to disable scheduler",
            "details": str(e),
        }), 500


@blueprint.route("/attach", methods=["POST"])
def attach_scheduler_engine() -> tuple[Dict[str, Any], int]:
    """Attach/re-attach to the scheduler engine.
    
    This is used when the scheduler engine is reinitialized.
    
    Body (optional):
        {
            "interval_seconds": 300  # Optional interval override
        }
    
    Returns:
        Updated status.
    """
    try:
        # This endpoint is a no-op in the API layer
        # The actual attachment happens in core_setup.py
        # This endpoint exists for documentation and potential future use
        body = request.get_json() or {}
        
        integration = get_hold_scheduler_integration()
        if "interval_seconds" in body:
            integration.set_interval(int(body["interval_seconds"]))
        
        return jsonify({
            "status": "attach_requested",
            "note": "Scheduler attachment is handled in core_setup.py",
            "current_status": integration.get_job_status(),
        }), 200
    except Exception as e:
        logger.exception("Failed to process attach request")
        return jsonify({
            "error": "Failed to process attach request",
            "details": str(e),
        }), 500
