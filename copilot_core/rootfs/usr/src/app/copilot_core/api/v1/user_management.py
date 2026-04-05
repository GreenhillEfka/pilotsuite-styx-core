"""User-management API bridge for RBAC/runtime summaries."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token

user_management_bp = Blueprint("user_management", __name__, url_prefix="/api/v1/user-management")

# Stub engine - replace with real implementation when available
class _StubEngine:
    def get_user_management_summary(self):
        return {"status": "stub"}
    @property
    def _roles(self):
        return {}

_engine = _StubEngine()


@user_management_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


@user_management_bp.get("/summary")
def get_summary():
    return jsonify({"ok": True, "summary": _engine.get_user_management_summary()})


@user_management_bp.get("/roles")
def list_roles():
    roles = [r.to_dict() if hasattr(r, 'to_dict') else r for r in _engine._roles.values()]
    return jsonify({"ok": True, "roles": roles, "count": len(roles)})


@user_management_bp.post("/users")
def create_user():
    data = request.get_json() or {}
    return jsonify({"ok": True, "user_id": data.get("user_id", "stub")})


@user_management_bp.post("/users/<user_id>/enable")
def enable_user(user_id: str):
    return jsonify({"ok": True, "user_id": user_id, "enabled": True})


@user_management_bp.post("/users/<user_id>/disable")
def disable_user(user_id: str):
    return jsonify({"ok": True, "user_id": user_id, "enabled": False})


__all__ = ["user_management_bp"]
