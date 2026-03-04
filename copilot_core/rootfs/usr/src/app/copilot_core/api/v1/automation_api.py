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
from copilot_core.api.validation import validate_json
from copilot_core.api.v1.schemas import AutomationCreateSchema
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
@validate_json(AutomationCreateSchema)
def create_automation(body: AutomationCreateSchema):
    """Create an HA automation from a suggestion (Pydantic-validated)."""
    creator = _get_creator()
    if creator is None:
        return jsonify({
            "ok": False,
            "error": "AutomationCreator not initialized",
            "code": "SERVICE_UNAVAILABLE",
        }), 503

    data = body.model_dump()
    result = creator.create_from_suggestion(data)

    if result.get("ok"):
        return jsonify(result), 201

    # Structured error codes instead of string matching
    error_msg = result.get("error", "")
    if "SUPERVISOR_TOKEN" in error_msg:
        result["code"] = "SUPERVISOR_UNAVAILABLE"
        status = 503
    elif "Cannot parse" in error_msg:
        result["code"] = "PARSE_ERROR"
        status = 422
    elif "HA API error" in error_msg:
        result["code"] = "HA_API_ERROR"
        status = 502
    else:
        result["code"] = "INTERNAL_ERROR"
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
