"""Zone Automation API — REST API für Zone Automation (CORE).

DIESE API ist die EINZIGE Schnittstelle zwischen CORE und HA.

HA ruft diese APIs auf:
- GET /api/v1/zone-automation/dashboard — Dashboard Daten
- GET /api/v1/zone-automation/zones — Alle Zonen
- GET /api/v1/zone-automation/zones/{zone_id} — Zone Details
- PUT /api/v1/zone-automation/zones/{zone_id}/config — Config setzen
- PUT /api/v1/zone-automation/zones/{zone_id}/neuron/{neuron_id}/mode — Neuron Mode
- GET /api/v1/zone-automation/zones/{zone_id}/rules — Rules für Zone
- POST /api/v1/zone-automation/zones/{zone_id}/rules — Rule erstellen
- POST /api/v1/zone-automation/zones/{zone_id}/event — Event verarbeiten
- POST /api/v1/zone-automation/zones/{zone_id}/test — Rule testen

HA macht KEINE Logik — nur API-Calls!
"""

from flask import Blueprint, jsonify, request
from typing import Any, Dict
import logging

_LOGGER = logging.getLogger(__name__)

zone_automation_api_bp = Blueprint('zone_automation_api', __name__, url_prefix='/api/v1/zone-automation')

# Global controller reference (wird bei Init gesetzt)
_controller = None


def init_zone_automation_api(controller) -> None:
    """Controller initialisieren."""
    global _controller
    _controller = controller
    _LOGGER.info("Zone Automation API initialized")


# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================

@zone_automation_api_bp.route('/dashboard', methods=['GET'])
def get_dashboard() -> Dict[str, Any]:
    """Dashboard Daten für alle Zonen."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    return jsonify(_controller.get_dashboard_data())


@zone_automation_api_bp.route('/stats', methods=['GET'])
def get_stats() -> Dict[str, Any]:
    """Statistiken."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    return jsonify(_controller.stats)


# =============================================================================
# ZONE ENDPOINTS
# =============================================================================

@zone_automation_api_bp.route('/zones', methods=['GET'])
def get_zones() -> Dict[str, Any]:
    """Alle Zonen."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    zones = {
        zone_id: config.to_dict()
        for zone_id, config in _controller._configs.items()
    }
    
    return jsonify({
        "zones": zones,
        "total": len(zones),
    })


@zone_automation_api_bp.route('/zones/<zone_id>', methods=['GET'])
def get_zone(zone_id: str) -> Dict[str, Any]:
    """Zone Details."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    config = _controller.get_zone_config(zone_id)
    if not config:
        return jsonify({"error": f"Zone {zone_id} not found"}), 404
    
    return jsonify(config.to_dict())


@zone_automation_api_bp.route('/zones/<zone_id>/config', methods=['PUT'])
def set_zone_config(zone_id: str) -> Dict[str, Any]:
    """Zone Config setzen."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        config = _controller.set_zone_config(zone_id, data)
        return jsonify({
            "success": True,
            "zone_id": zone_id,
            "config": config.to_dict(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@zone_automation_api_bp.route('/zones/<zone_id>/neuron/<neuron_id>/mode', methods=['PUT'])
def set_neuron_mode(zone_id: str, neuron_id: str) -> Dict[str, Any]:
    """Neuron Mode setzen."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    data = request.get_json()
    if not data or 'mode' not in data:
        return jsonify({"error": "Mode required"}), 400
    
    try:
        from .zone_automation_controller import NeuronMode
        mode = NeuronMode(data['mode'])
        _controller.update_neuron_mode(zone_id, neuron_id, mode)
        
        return jsonify({
            "success": True,
            "zone_id": zone_id,
            "neuron_id": neuron_id,
            "mode": mode.value,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# RULE ENDPOINTS
# =============================================================================

@zone_automation_api_bp.route('/zones/<zone_id>/rules', methods=['GET'])
def get_zone_rules(zone_id: str) -> Dict[str, Any]:
    """Rules für Zone."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    rules = _controller._rule_engine.get_rules_for_zone(zone_id)
    
    return jsonify({
        "zone_id": zone_id,
        "rules": [rule.to_dict() for rule in rules],
        "total": len(rules),
    })


@zone_automation_api_bp.route('/zones/<zone_id>/rules', methods=['POST'])
def create_rule(zone_id: str) -> Dict[str, Any]:
    """Rule erstellen."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    required = ['name', 'trigger', 'action']
    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} required"}), 400
    
    try:
        from .zone_automation_controller import AutomationMode
        
        rule_id = _controller._rule_engine.create_rule(
            zone_id=zone_id,
            name=data['name'],
            description=data.get('description', ''),
            trigger=data['trigger'],
            condition=data.get('condition', {}),
            action=data['action'],
            mode=AutomationMode(data.get('mode', 'learning')),
        )
        
        return jsonify({
            "success": True,
            "rule_id": rule_id,
            "zone_id": zone_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# EVENT PROCESSING
# =============================================================================

@zone_automation_api_bp.route('/zones/<zone_id>/event', methods=['POST'])
def process_event(zone_id: str) -> Dict[str, Any]:
    """Event verarbeiten (Haupt-Endpoint für HA)."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    event_type = data.get('event_type', 'state_changed')
    context = data.get('context', {})
    
    result = _controller.process_event(zone_id, event_type, context)
    
    return jsonify(result)


# =============================================================================
# TESTING
# =============================================================================

@zone_automation_api_bp.route('/zones/<zone_id>/test', methods=['POST'])
def test_rule(zone_id: str) -> Dict[str, Any]:
    """Rule testen (Simulation)."""
    if not _controller:
        return jsonify({"error": "Controller not initialized"}), 500
    
    data = request.get_json()
    if not data or 'context' not in data:
        return jsonify({"error": "Context required"}), 400
    
    context = data['context']
    triggered_rules = _controller._rule_engine.check_trigger(context)
    
    # Filter by zone
    zone_rules = [r for r in triggered_rules if r.zone_id == zone_id]
    
    return jsonify({
        "zone_id": zone_id,
        "context": context,
        "triggered_rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "mode": r.mode.value,
                "would_execute": r.action,
            }
            for r in zone_rules
        ],
        "total": len(zone_rules),
    })


# =============================================================================
# HEALTH CHECK
# =============================================================================

@zone_automation_api_bp.route('/health', methods=['GET'])
def health_check() -> Dict[str, Any]:
    """Health Check."""
    return jsonify({
        "status": "healthy" if _controller else "unhealthy",
        "controller_initialized": _controller is not None,
    })
