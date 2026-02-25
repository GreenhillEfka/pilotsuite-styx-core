"""
Automation Webhook Trigger - PilotSuite v7.13.0

Trigger Automations via Webhook.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

automation_webhook_bp = Blueprint("automation_webhook", __name__, url_prefix="/api/v1/automation")


@automation_webhook_bp.route("/trigger/<automation_id>", methods=["POST"])
@require_token
def trigger_automation(automation_id):
    """Trigger a specific automation by ID."""
    hass = None
    try:
        from homeassistant.core import HomeAssistant
        hass = HomeAssistant.get()
    except Exception:
        pass
    
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        # Call the automation trigger service
        hass.services.call("automation", "trigger", {"entity_id": automation_id})
        return jsonify({
            "ok": True,
            "automation_id": automation_id,
            "message": "Automation triggered",
        })
    except Exception as e:
        logger.error(f"Failed to trigger automation: {e}")
        return jsonify({"error": str(e)}), 500


@automation_webhook_bp.route("/trigger_by_alias/<alias>", methods=["POST"])
@require_token
def trigger_by_alias(alias):
    """Trigger automation by alias name."""
    hass = None
    try:
        from homeassistant.core import HomeAssistant
        hass = HomeAssistant.get()
    except Exception:
        pass
    
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    # Find automation by alias/friendly name
    try:
        all_states = list(hass.states.async_all())
        automations = [s for s in all_states if s.domain == "automation"]
        
        matched = None
        for a in automations:
            attrs = dict(a.attributes) if a.attributes else {}
            if alias.lower() in a.entity_id.lower():
                matched = a.entity_id
                break
            if "friendly_name" in attrs and alias.lower() in attrs["friendly_name"].lower():
                matched = a.entity_id
                break
        
        if not matched:
            return jsonify({"error": "Automation not found"}), 404
        
        hass.services.call("automation", "trigger", {"entity_id": matched})
        return jsonify({
            "ok": True,
            "automation_id": matched,
            "message": "Automation triggered",
        })
    except Exception as e:
        logger.error(f"Failed to trigger automation: {e}")
        return jsonify({"error": str(e)}), 500


@automation_webhook_bp.route("/list", methods=["GET"])
@require_token
def list_automations():
    """List all automations."""
    hass = None
    try:
        from homeassistant.core import HomeAssistant
        hass = HomeAssistant.get()
    except Exception:
        pass
    
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        all_states = list(hass.states.async_all())
        automations = [
            {
                "entity_id": a.entity_id,
                "state": a.state,
                "friendly_name": a.attributes.get("friendly_name") if a.attributes else None,
                "last_triggered": a.attributes.get("last_triggered") if a.attributes else None,
            }
            for a in all_states if a.domain == "automation"
        ]
        
        return jsonify({
            "ok": True,
            "automations": automations,
            "count": len(automations),
        })
    except Exception as e:
        logger.error(f"Failed to list automations: {e}")
        return jsonify({"error": str(e)}), 500
