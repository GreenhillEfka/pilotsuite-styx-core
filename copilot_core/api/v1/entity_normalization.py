"""Entity-normalization API bridge.

Exposes a small Flask surface over the runtime normalization engine so the
registry points at a real blueprint instead of a missing module.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.integration.entity_normalization import create_entity_normalization_engine

entity_normalization_bp = Blueprint(
    "entity_normalization",
    __name__,
    url_prefix="/api/v1/entity-normalization",
)

_ENTITY_NORMALIZATION_ENGINE = None


def _get_engine():
    global _ENTITY_NORMALIZATION_ENGINE
    if _ENTITY_NORMALIZATION_ENGINE is None:
        _ENTITY_NORMALIZATION_ENGINE = create_entity_normalization_engine()
    return _ENTITY_NORMALIZATION_ENGINE


@entity_normalization_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


@entity_normalization_bp.get("/health")
def get_health():
    engine = _get_engine()
    return jsonify({"ok": True, "statistics": engine.get_statistics()})


@entity_normalization_bp.get("/mappings")
def list_mappings():
    engine = _get_engine()
    zone_id = request.args.get("zone_id")
    return jsonify({"ok": True, "mappings": engine.list_mappings(zone_id=zone_id)})


@entity_normalization_bp.get("/zones/<zone_id>")
def get_zone(zone_id: str):
    engine = _get_engine()
    registry = engine.get_zone_registry(zone_id)
    zone_states = engine.get_zone_states(zone_id)
    return jsonify(
        {
            "ok": True,
            "zone_id": zone_id,
            "registry": registry.to_dict() if registry else None,
            "states": {key: value.to_dict() for key, value in zone_states.items()},
        }
    )


__all__ = ["entity_normalization_bp"]
