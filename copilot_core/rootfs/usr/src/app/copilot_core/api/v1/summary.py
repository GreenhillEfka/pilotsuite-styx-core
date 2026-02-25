"""
System Summary API - PilotSuite v7.19.0

Comprehensive system overview endpoint.
"""

from flask import Blueprint, jsonify, request
import logging
import time

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

summary_bp = Blueprint("summary", __name__, url_prefix="/api/v1/summary")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@summary_bp.route("", methods=["GET"])
@require_token
def get_summary():
    """Get comprehensive system summary."""
    from flask import current_app
    
    hass = _get_ha_hass()
    
    # Base summary
    summary = {
        "ok": True,
        "timestamp": time.time(),
    }
    
    if hass:
        try:
            all_states = list(hass.states.async_all())
            
            # Count by domain
            domains = {}
            for s in all_states:
                d = s.domain
                domains[d] = domains.get(d, 0) + 1
            
            # Count by state
            states_count = {}
            for s in all_states:
                st = s.state
                states_count[st] = states_count.get(st, 0) + 1
            
            summary["entities"] = {
                "total": len(all_states),
                "by_domain": domains,
                "by_state": states_count,
            }
            
            # Key entities
            lights_on = sum(1 for s in all_states if s.domain == "light" and s.state == "on")
            summary["lights"] = {"on": lights_on}
            
            # Climate
            climate = [s for s in all_states if s.domain == "climate"]
            if climate:
                summary["climate"] = {
                    "devices": len(climate),
                    "current_states": [c.state for c in climate[:5]],
                }
            
        except Exception as e:
            summary["entities_error"] = str(e)
    
    # Services
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        summary["services"] = {
            "brain_graph": services.get("brain_graph_service") is not None,
            "conversation_memory": services.get("conversation_memory") is not None,
            "module_registry": services.get("module_registry") is not None,
            "hub_dashboard": services.get("hub_dashboard") is not None,
        }
    except Exception:
        pass
    
    return jsonify(summary)


@summary_bp.route("/quick", methods=["GET"])
@require_token
def quick_summary():
    """Quick summary for dashboard cards."""
    hass = _get_ha_hass()
    
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        all_states = list(hass.states.async_all())
        
        lights_on = sum(1 for s in all_states if s.domain == "light" and s.state == "on")
        lights_total = sum(1 for s in all_states if s.domain == "light")
        
        switches_on = sum(1 for s in all_states if s.domain == "switch" and s.state == "on")
        switches_total = sum(1 for s in all_states if s.domain == "switch")
        
        sensors = [s for s in all_states if s.domain == "sensor"]
        
        return jsonify({
            "ok": True,
            "lights": {"on": lights_on, "total": lights_total},
            "switches": {"on": switches_on, "total": switches_total},
            "sensors": len(sensors),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
