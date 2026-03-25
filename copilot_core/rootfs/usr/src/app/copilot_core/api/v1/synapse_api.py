"""Synapse Layer API Endpoints — HA entity ↔ Core neuron mapping.

This module provides the REST API for the Synapse layer, enabling:
- Ingesting HA webhook events
- Resolving entity_id → neuron_id
- Querying dynamic neurons
- Zone presence tracking

Endpoints:
  POST /api/v1/synapse/feed           — Feed HA event
  GET  /api/v1/synapse/resolve/<eid>  — Get neuron_id for entity
  GET  /api/v1/neurons/dynamic/<type> — Get dynamic neurons by type
  GET  /api/v1/presence/zone/<id>     — Get zone presence
  GET  /api/v1/synapse/contracts      — List all synapse contracts
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("synapse", __name__, url_prefix="/api/v1")

# Global references (injected via init function)
_neuron_feeder: Optional[Any] = None
_dynamic_creator: Optional[Any] = None
_zone_presence: Optional[Any] = None
_synapse_integrator: Optional[Any] = None


def init_synapse_api(
    neuron_feeder: Optional[Any] = None,
    dynamic_creator: Optional[Any] = None,
    zone_presence: Optional[Any] = None,
    synapse_integrator: Optional[Any] = None,
) -> None:
    """Initialize the Synapse API with required services."""
    global _neuron_feeder, _dynamic_creator, _zone_presence, _synapse_integrator
    _neuron_feeder = neuron_feeder
    _dynamic_creator = dynamic_creator
    _zone_presence = zone_presence
    _synapse_integrator = synapse_integrator
    _LOGGER.info("Synapse API initialized")


# =============================================================================
# Auth middleware
# =============================================================================

@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required"
        }), 401


# =============================================================================
# POST /api/v1/synapse/feed — Feed HA event
# =============================================================================

@bp.route("/synapse/feed", methods=["POST"])
def synapse_feed():
    """Feed a Home Assistant event into the neural system.

    Request Body:
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"brightness": 255},
            "last_changed": "2026-03-25T07:45:00+00:00"  // optional
        }

    Returns:
        {
            "status": "ok",
            "entity_id": "light.living_room",
            "neuron_id": "state.light_living_room",
            "neuron_type": "state",
            "dynamic_created": false
        }
    """
    try:
        data = request.get_json() or {}
        entity_id = data.get("entity_id")
        state = data.get("state")
        attributes = data.get("attributes", {})

        if not entity_id:
            return jsonify({"error": "missing_entity_id"}), 400
        if state is None:
            return jsonify({"error": "missing_state"}), 400

        # Lazy import to avoid circular deps
        if _neuron_feeder is None:
            from copilot_core.neurons.feeding import NeuronFeeder
            feeder = NeuronFeeder()
        else:
            feeder = _neuron_feeder

        result = feeder.feed(
            entity_id=entity_id,
            state=state,
            attributes=attributes,
        )

        return jsonify({
            "status": "ok",
            "entity_id": result.entity_id,
            "neuron_id": result.neuron_id,
            "neuron_type": result.neuron_type,
            "dynamic_created": result.dynamic_created,
        })

    except Exception as e:
        _LOGGER.error("Failed to feed synapse event: %s", e)
        return jsonify({"error": "feed_failed", "message": str(e)}), 500


# =============================================================================
# POST /api/v1/synapse/batch — Batch feed HA events
# =============================================================================

@bp.route("/synapse/batch", methods=["POST"])
def synapse_batch_feed():
    """Feed multiple Home Assistant events in one batch.

    Request Body:
        {
            "events": [
                {"entity_id": "...", "state": "...", "attributes": {...}},
                ...
            ]
        }

    Returns:
        {
            "status": "ok",
            "results": [{...}, ...]
        }
    """
    try:
        data = request.get_json() or {}
        events = data.get("events", [])

        if not isinstance(events, list):
            return jsonify({"error": "events_must_be_array"}), 400

        from copilot_core.neurons.feeding import NeuronFeeder, FeedEvent
        feeder = _neuron_feeder if _neuron_feeder else NeuronFeeder()

        feed_events = []
        for evt in events:
            if not isinstance(evt, dict):
                continue
            feed_events.append(FeedEvent(
                entity_id=evt.get("entity_id", ""),
                state=evt.get("state"),
                attributes=evt.get("attributes", {}),
            ))

        results = feeder.batch_feed(feed_events)

        return jsonify({
            "status": "ok",
            "count": len(results),
            "results": [
                {
                    "entity_id": r.entity_id,
                    "neuron_id": r.neuron_id,
                    "neuron_type": r.neuron_type,
                    "dynamic_created": r.dynamic_created,
                }
                for r in results
            ],
        })

    except Exception as e:
        _LOGGER.error("Failed to batch feed synapse events: %s", e)
        return jsonify({"error": "batch_feed_failed", "message": str(e)}), 500


# =============================================================================
# GET /api/v1/synapse/resolve/<entity_id> — Resolve entity to neuron
# =============================================================================

@bp.route("/synapse/resolve/<path:entity_id>", methods=["GET"])
def synapse_resolve(entity_id: str):
    """Resolve a Home Assistant entity_id to its neuron_id.

    Path Parameters:
        entity_id: HA entity ID (e.g. "light.living_room")

    Returns:
        {
            "entity_id": "light.living_room",
            "neuron_id": "state.light_living_room",
            "neuron_type": "state",
            "found": true
        }
    """
    try:
        from copilot_core.neurons.feeding import NeuronFeeder
        feeder = _neuron_feeder if _neuron_feeder else NeuronFeeder()

        neuron_id = feeder.get_neuron_id(entity_id)
        contract = feeder.get_contract(entity_id)

        if neuron_id:
            return jsonify({
                "entity_id": entity_id,
                "neuron_id": neuron_id,
                "neuron_type": contract.neuron_type if contract else "unknown",
                "found": True,
            })

        # No contract yet - return predicted mapping
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
        type_map = {
            "sensor": "context",
            "binary_sensor": "context",
            "climate": "context",
            "weather": "context",
            "light": "state",
            "switch": "state",
            "fan": "state",
            "person": "presence",
            "device_tracker": "presence",
        }
        predicted_type = type_map.get(domain, "state")
        predicted_neuron_id = f"{predicted_type}.{entity_id.replace('.', '_')}"

        return jsonify({
            "entity_id": entity_id,
            "neuron_id": predicted_neuron_id,
            "neuron_type": predicted_type,
            "found": False,
            "note": "Contract not yet established - prediction based on domain",
        }), 404

    except Exception as e:
        _LOGGER.error("Failed to resolve entity %s: %s", entity_id, e)
        return jsonify({"error": "resolve_failed", "message": str(e)}), 500


# =============================================================================
# GET /api/v1/synapse/contracts — List all synapse contracts
# =============================================================================

@bp.route("/synapse/contracts", methods=["GET"])
def synapse_contracts():
    """List all established synapse contracts (entity_id → neuron_id mappings).

    Query Parameters:
        neuron_type (str): Filter by neuron type (context|state|presence|energy)

    Returns:
        {
            "contracts": [
                {
                    "entity_id": "light.living_room",
                    "neuron_id": "state.light_living_room",
                    "neuron_type": "state",
                    "domain": "light"
                },
                ...
            ],
            "total": 42
        }
    """
    try:
        from copilot_core.neurons.feeding import NeuronFeeder
        feeder = _neuron_feeder if _neuron_feeder else NeuronFeeder()

        contracts = feeder.get_all_contracts()
        neuron_type_filter = request.args.get("neuron_type")

        result = []
        for entity_id, contract in contracts.items():
            if neuron_type_filter and contract.neuron_type != neuron_type_filter:
                continue
            result.append({
                "entity_id": contract.entity_id,
                "neuron_id": contract.neuron_id,
                "neuron_type": contract.neuron_type,
                "domain": contract.domain,
            })

        return jsonify({
            "contracts": result,
            "total": len(result),
            "filter": neuron_type_filter,
        })

    except Exception as e:
        _LOGGER.error("Failed to list contracts: %s", e)
        return jsonify({"error": "contracts_failed", "message": str(e)}), 500


# =============================================================================
# GET /api/v1/neurons/dynamic/<neuron_type> — Get dynamic neurons
# =============================================================================

@bp.route("/neurons/dynamic/<neuron_type>", methods=["GET"])
def dynamic_neurons(neuron_type: str):
    """Get all dynamic neurons of a specific type.

    Path Parameters:
        neuron_type: Neuron type filter (context|state|presence|energy|meta)

    Returns:
        {
            "neuron_type": "context",
            "neurons": [{...}, ...],
            "total": 5
        }
    """
    try:
        if _dynamic_creator is None:
            from copilot_core.neurons.dynamic import DynamicNeuronFactory
            creator = DynamicNeuronFactory()
        else:
            creator = _dynamic_creator

        neurons = creator.get_by_type(neuron_type)

        return jsonify({
            "neuron_type": neuron_type,
            "neurons": neurons,
            "total": len(neurons),
        })

    except Exception as e:
        _LOGGER.error("Failed to get dynamic neurons: %s", e)
        return jsonify({"error": "dynamic_query_failed", "message": str(e)}), 500


# =============================================================================
# GET /api/v1/neurons/dynamic — Get all dynamic neurons
# =============================================================================

@bp.route("/neurons/dynamic", methods=["GET"])
def all_dynamic_neurons():
    """Get all dynamic neurons.

    Returns:
        {
            "neurons": [{...}, ...],
            "total": 10,
            "max_allowed": 10
        }
    """
    try:
        if _dynamic_creator is None:
            from copilot_core.neurons.dynamic import DynamicNeuronFactory
            creator = DynamicNeuronFactory()
        else:
            creator = _dynamic_creator

        neurons = creator.get_dynamic_neurons()
        stats = creator.get_stats()

        return jsonify({
            "neurons": neurons,
            "total": len(neurons),
            "max_allowed": stats.get("max_neurons", 10),
        })

    except Exception as e:
        _LOGGER.error("Failed to get dynamic neurons: %s", e)
        return jsonify({"error": "dynamic_query_failed", "message": str(e)}), 500


# =============================================================================
# GET /api/v1/presence/zone/<zone_id> — Get zone presence
# =============================================================================

@bp.route("/presence/zone/<zone_id>", methods=["GET"])
def zone_presence(zone_id: str):
    """Get presence state for a specific zone.

    Path Parameters:
        zone_id: Zone identifier (e.g. "living", "bedroom", "kitchen")

    Returns:
        {
            "zone_id": "living",
            "presence": true,
            "confidence": 0.95,
            "last_seen": "2026-03-25T07:45:00+00:00",
            "last_changed": "2026-03-25T07:30:00+00:00"
        }
    """
    try:
        from copilot_core.neurons.presence import get_zone_presence_manager
        manager = _zone_presence if _zone_presence else get_zone_presence_manager()

        result = manager.get_zone_presence(zone_id)
        result["zone_id"] = zone_id

        return jsonify(result)

    except Exception as e:
        _LOGGER.error("Failed to get zone presence: %s", e)
        return jsonify({"error": "presence_failed", "message": str(e)}), 500


# =============================================================================
# GET /api/v1/presence/zones — Get all zone presence states
# =============================================================================

@bp.route("/presence/zones", methods=["GET"])
def all_zone_presence():
    """Get presence state for all registered zones.

    Returns:
        {
            "zones": {
                "living": {"presence": true, ...},
                "bedroom": {"presence": false, ...},
                ...
            }
        }
    """
    try:
        from copilot_core.neurons.presence import get_zone_presence_manager
        manager = _zone_presence if _zone_presence else get_zone_presence_manager()

        zones = manager.get_all_zones()

        return jsonify({
            "zones": zones,
            "total": len(zones),
        })

    except Exception as e:
        _LOGGER.error("Failed to get zone presence: %s", e)
        return jsonify({"error": "presence_failed", "message": str(e)}), 500


# =============================================================================
# GET /api/v1/synapse/integration/automations — Get automation synapses
# =============================================================================

@bp.route("/synapse/integration/automations", methods=["GET"])
def automation_synapses():
    """Get all automation synapses.

    Returns:
        {
            "automations": [
                {
                    "automation_id": "...",
                    "name": "...",
                    "neuron_ids": [...],
                    "trigger_entities": [...],
                    ...
                }
            ],
            "total": 42
        }
    """
    try:
        from copilot_core.automation.synapse_integration import get_synapse_integrator
        integrator = _synapse_integrator if _synapse_integrator else get_synapse_integrator()

        automations = integrator.get_all_synapses()

        return jsonify({
            "automations": automations,
            "total": len(automations),
        })

    except Exception as e:
        _LOGGER.error("Failed to get automation synapses: %s", e)
        return jsonify({"error": "automation_query_failed", "message": str(e)}), 500


# =============================================================================
# GET /api/v1/synapse/integration/zone/<zone_id> — Get zone automation synapses
# =============================================================================

@bp.route("/synapse/integration/zone/<zone_id>", methods=["GET"])
def zone_synapses(zone_id: str):
    """Get full synapse map for a zone.

    Returns:
        {
            "zone_id": "living",
            "automation_count": 5,
            "neuron_ids": [...],
            "synapses": [...]
        }
    """
    try:
        from copilot_core.automation.synapse_integration import get_synapse_integrator
        integrator = _synapse_integrator if _synapse_integrator else get_synapse_integrator()

        result = integrator.get_zone_synapses(zone_id)

        return jsonify(result)

    except Exception as e:
        _LOGGER.error("Failed to get zone synapses: %s", e)
        return jsonify({"error": "zone_synapses_failed", "message": str(e)}), 500
