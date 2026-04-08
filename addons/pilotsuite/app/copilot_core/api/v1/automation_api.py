"""
Automation API -- Create and manage HA automations from suggestions.

Endpoints:
  POST /api/v1/automations/create   -- Create automation from suggestion
  GET  /api/v1/automations           -- List Styx-created automations

All endpoints require a valid auth token (Bearer or X-Auth-Token).
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.automation_creator import AutomationCreator

_LOGGER = logging.getLogger(__name__)

# Blueprint with relative prefix -- registered under /api/v1 in blueprint.py
automation_bp = Blueprint(
    "automations", __name__, url_prefix="/automations"
)

# Global creator reference, set by init_automation_api()
_creator: Optional[AutomationCreator] = None


def init_automation_api(creator: AutomationCreator) -> None:
    """Wire the AutomationCreator instance into the blueprint.

    Called from ``core_setup.init_services()`` or ``register_blueprints()``.
    """
    global _creator
    _creator = creator
    _LOGGER.info("Automation API initialized")


def _get_creator() -> Optional[AutomationCreator]:
    """Return the active creator instance."""
    return _creator


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@automation_bp.route("/create", methods=["POST"])
@require_token
def create_automation():
    """Create an HA automation from a suggestion.

    Request body::

        {
            "antecedent": "When the sun sets",
            "consequent": "Turn on light.living_room",
            "alias":      "Sunset living room lights"   // optional
        }

    Response (success)::

        {
            "ok": true,
            "automation_id": "styx_a1b2c3d4e5f6",
            "alias": "Sunset living room lights"
        }

    Response (failure)::

        {
            "ok": false,
            "error": "Cannot parse trigger: ..."
        }
    """
    creator = _get_creator()
    if creator is None:
        return jsonify({
            "ok": False,
            "error": "AutomationCreator not initialized",
        }), 503

    data = request.get_json(silent=True) or {}

    if not data.get("antecedent") or not data.get("consequent"):
        return jsonify({
            "ok": False,
            "error": "Both 'antecedent' and 'consequent' fields are required",
        }), 400

    result = creator.create_from_suggestion(data)

    if result.get("ok"):
        return jsonify(result), 201
    else:
        # Determine appropriate HTTP status based on error type
        error_msg = result.get("error", "")
        if "SUPERVISOR_TOKEN" in error_msg:
            status = 503
        elif "Cannot parse" in error_msg:
            status = 422
        elif "HA API error" in error_msg:
            status = 502
        else:
            status = 500
        return jsonify(result), status


@automation_bp.route("/", methods=["GET"])
@require_token
def list_automations():
    """List all automations created by Styx in this session.

    Response::

        {
            "ok": true,
            "count": 2,
            "automations": [
                {
                    "automation_id": "styx_a1b2c3d4e5f6",
                    "alias": "Sunset living room lights",
                    "created_at": 1708300000.0,
                    "antecedent": "When the sun sets",
                    "consequent": "Turn on light.living_room"
                },
                ...
            ]
        }
    """
    creator = _get_creator()
    if creator is None:
        return jsonify({
            "ok": False,
            "error": "AutomationCreator not initialized",
        }), 503

    automations = creator.list_created()
    return jsonify({
        "ok": True,
        "count": len(automations),
        "automations": automations,
    })
