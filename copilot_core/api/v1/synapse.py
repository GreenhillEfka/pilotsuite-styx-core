"""Synapse API (Flask Blueprint) — HA Entity ↔ Core Neuron Mapping Layer.

Endpoints:
  - POST /api/v1/synapse/feed           — ingest HA entity event
  - GET  /api/v1/synapse/resolve/<eid>  — entity_id → neuron_id
  - GET  /api/v1/synapse/entity/<eid>   — get synapse links for entity
  - GET  /api/v1/synapse/zone/<zone>    — all synapse links for zone
  - POST /api/v1/synapse/register        — register automation synapse
  - GET  /api/v1/synapse/automations    — list all registered synapse links
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.automation.synapse_integration import (
    get_synapse_registry,
    resolve_entity_to_neuron,
    register_automation_synapse,
    get_zone_automation_synapses,
    get_affected_automations_on_entity_change,
)
from copilot_core.neurons.feeding import NeuronFeeder

logger = logging.getLogger(__name__)

bp = Blueprint("synapse", __name__, url_prefix="/synapse")


# === POST /api/v1/synapse/feed ===

@bp.route("/feed", methods=["POST"])
def synapse_feed():
    """
    POST /api/v1/synapse/feed
    Body: {"entity_id": "light.living_room", "state": "on", "attributes": {}, "trigger_presence_change": false}
    """
    try:
        body = request.get_json(force=True) or {}
        entity_id = body.get("entity_id")
        state = body.get("state")
        attributes = body.get("attributes", {})
        last_changed = body.get("last_changed")

        feeder = NeuronFeeder()
        neuron_id = feeder.feed(
            entity_id=entity_id,
            state=state,
            attributes=attributes,
            last_changed=last_changed,
        )

        affected = get_affected_automations_on_entity_change(entity_id)

        return jsonify({
            "entity_id": entity_id,
            "neuron_id": neuron_id,
            "fed": True,
            "affected_automations": affected,
        })

    except Exception as e:
        logger.error(f"Synapse feed error: {e}")
        return jsonify({"error": str(e)}), 500


# === GET /api/v1/synapse/resolve/<entity_id> ===

@bp.route("/resolve/<entity_id>", methods=["GET"])
def synapse_resolve(entity_id: str):
    """
    GET /api/v1/synapse/resolve/light.living_room
    """
    try:
        neuron_id = resolve_entity_to_neuron(entity_id)
        neuron_type = neuron_id.split(".")[0] if "." in neuron_id else "unknown"

        return jsonify({
            "entity_id": entity_id,
            "neuron_id": neuron_id,
            "neuron_type": neuron_type,
        })

    except Exception as e:
        logger.error(f"Synapse resolve error: {e}")
        return jsonify({"error": str(e)}), 500


# === GET /api/v1/synapse/entity/<entity_id> ===

@bp.route("/entity/<entity_id>", methods=["GET"])
def synapse_entity(entity_id: str):
    """Get all synapse links (automations) involving this entity."""
    try:
        registry = get_synapse_registry()
        links = registry.get_automations_for_entity(entity_id)

        return jsonify({
            "entity_id": entity_id,
            "automation_count": len(links),
            "automations": [
                {
                    "automation_id": link.automation_id,
                    "automation_name": link.automation_name,
                    "zone_id": link.zone_id,
                    "neuron_ids": link.neuron_ids,
                }
                for link in links
            ],
        })

    except Exception as e:
        logger.error(f"Synapse entity error: {e}")
        return jsonify({"error": str(e)}), 500


# === GET /api/v1/synapse/zone/<zone_id> ===

@bp.route("/zone/<zone_id>", methods=["GET"])
def synapse_zone(zone_id: str):
    """Get all synapse links for automations in a zone."""
    try:
        links = get_zone_automation_synapses(zone_id)

        return jsonify({
            "zone_id": zone_id,
            "automation_count": len(links),
            "automations": [
                {
                    "automation_id": link.automation_id,
                    "automation_name": link.automation_name,
                    "trigger_entities": link.trigger_entities,
                    "condition_entities": link.condition_entities,
                    "action_entities": link.action_entities,
                    "neuron_ids": link.neuron_ids,
                }
                for link in links
            ],
        })

    except Exception as e:
        logger.error(f"Synapse zone error: {e}")
        return jsonify({"error": str(e)}), 500


# === POST /api/v1/synapse/register ===

@bp.route("/register", methods=["POST"])
def synapse_register():
    """
    POST /api/v1/synapse/register
    Body: {"automation_id": "...", "automation_name": "...", "zone_id": "...",
           "trigger_entities": [], "condition_entities": [], "action_entities": []}
    """
    try:
        body = request.get_json(force=True) or {}
        link = register_automation_synapse(
            automation_id=body.get("automation_id"),
            automation_name=body.get("automation_name"),
            zone_id=body.get("zone_id"),
            trigger_entities=body.get("trigger_entities", []),
            condition_entities=body.get("condition_entities", []),
            action_entities=body.get("action_entities", []),
        )

        return jsonify({
            "automation_id": link.automation_id,
            "automation_name": link.automation_name,
            "zone_id": link.zone_id,
            "all_entities": link.all_entities,
            "neuron_ids": link.neuron_ids,
            "last_updated": link.last_updated.isoformat() if link.last_updated else None,
        })

    except Exception as e:
        logger.error(f"Synapse register error: {e}")
        return jsonify({"error": str(e)}), 500


# === GET /api/v1/synapse/automations ===

@bp.route("/automations", methods=["GET"])
def synapse_list_automations():
    """List all registered automation synapse links."""
    try:
        registry = get_synapse_registry()
        links = registry.list_all()

        return jsonify({
            "total": len(links),
            "automations": [
                {
                    "automation_id": link.automation_id,
                    "automation_name": link.automation_name,
                    "zone_id": link.zone_id,
                    "entity_count": len(link.all_entities),
                    "neuron_count": len(link.neuron_ids),
                }
                for link in links
            ],
        })

    except Exception as e:
        logger.error(f"Synapse list error: {e}")
        return jsonify({"error": str(e)}), 500
