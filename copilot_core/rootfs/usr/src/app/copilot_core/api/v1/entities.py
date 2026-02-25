"""
Entity Management API - PilotSuite v7.13.0

API für Entity-Discovery, -Status und -Steuerung.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

entities_bp = Blueprint("entities", __name__, url_prefix="/api/v1/entities")


def _get_ha_hass():
    """Get Home Assistant hass instance."""
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@entities_bp.route("", methods=["GET"])
@require_token
def list_entities():
    """List all Home Assistant entities.
    
    Query params:
    - domain: filter by domain (light, switch, sensor, etc.)
    - state: filter by state (on, off, unavailable)
    - limit: max results (default 100)
    """
    domain = request.args.get("domain")
    state_filter = request.args.get("state")
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        all_entities = list(hass.states.async_all())
        
        # Filter
        if domain:
            all_entities = [e for e in all_entities if e.domain == domain]
        if state_filter:
            all_entities = [e for e in all_entities if e.state == state_filter]
        
        # Limit
        all_entities = all_entities[:limit]
        
        entities = [
            {
                "entity_id": e.entity_id,
                "domain": e.domain,
                "state": e.state,
                "attributes": dict(e.attributes) if e.attributes else {},
                "last_changed": e.last_changed.isoformat() if e.last_changed else None,
            }
            for e in all_entities
        ]
        
        return jsonify({
            "ok": True,
            "entities": entities,
            "count": len(entities),
        })
    except Exception as e:
        logger.error(f"Failed to list entities: {e}")
        return jsonify({"error": str(e)}), 500


@entities_bp.route("/<entity_id>", methods=["GET"])
@require_token
def get_entity(entity_id):
    """Get specific entity details."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        state = hass.states.get(entity_id)
        if not state:
            return jsonify({"error": "Entity not found"}), 404
        
        return jsonify({
            "ok": True,
            "entity_id": state.entity_id,
            "domain": state.domain,
            "state": state.state,
            "attributes": dict(state.attributes) if state.attributes else {},
            "last_changed": state.last_changed.isoformat() if state.last_changed else None,
            "last_updated": state.last_updated.isoformat() if state.last_updated else None,
        })
    except Exception as e:
        logger.error(f"Failed to get entity: {e}")
        return jsonify({"error": str(e)}), 500


@entities_bp.route("/<entity_id>/set", methods=["POST"])
@require_token
def set_entity(entity_id):
    """Set entity state (for controllable entities)."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    data = request.get_json() or {}
    new_state = data.get("state")
    
    if not new_state:
        return jsonify({"error": "state required"}), 400
    
    try:
        hass.states.async_set(entity_id, new_state, data.get("attributes", {}))
        return jsonify({
            "ok": True,
            "entity_id": entity_id,
            "state": new_state,
        })
    except Exception as e:
        logger.error(f"Failed to set entity: {e}")
        return jsonify({"error": str(e)}), 500


@entities_bp.route("/domains", methods=["GET"])
@require_token
def list_domains():
    """List all available domains."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        all_entities = list(hass.states.async_all())
        domains = list(set(e.domain for e in all_entities))
        domains.sort()
        
        domain_counts = {}
        for d in domains:
            domain_counts[d] = sum(1 for e in all_entities if e.domain == d)
        
        return jsonify({
            "ok": True,
            "domains": domains,
            "counts": domain_counts,
        })
    except Exception as e:
        logger.error(f"Failed to list domains: {e}")
        return jsonify({"error": str(e)}), 500


@entities_bp.route("/search", methods=["GET"])
@require_token
def search_entities():
    """Search entities by name or state."""
    query = request.args.get("q", "").lower()
    if not query:
        return jsonify({"error": "query (q) parameter required"}), 400
    
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        all_entities = list(hass.states.async_all())
        
        # Search in entity_id, state, and attributes
        results = []
        for e in all_entities:
            if query in e.entity_id.lower() or query in e.state.lower():
                results.append({
                    "entity_id": e.entity_id,
                    "domain": e.domain,
                    "state": e.state,
                })
                continue
            
            # Search in attributes
            if e.attributes:
                for key, value in e.attributes.items():
                    if isinstance(value, str) and query in value.lower():
                        results.append({
                            "entity_id": e.entity_id,
                            "domain": e.domain,
                            "state": e.state,
                            "match": f"{key}: {value}",
                        })
                        break
        
        return jsonify({
            "ok": True,
            "results": results[:50],
            "count": len(results),
        })
    except Exception as e:
        logger.error(f"Failed to search entities: {e}")
        return jsonify({"error": str(e)}), 500
