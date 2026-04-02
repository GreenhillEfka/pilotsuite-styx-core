"""User-management API bridge for RBAC/runtime summaries."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token

from .users import _get_user_management_engine

user_management_bp = Blueprint("user_management", __name__, url_prefix="/api/v1/user-management")


@user_management_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


@user_management_bp.get("/summary")
def get_summary():
    engine = _get_user_management_engine()
    return jsonify({"ok": True, "summary": engine.get_user_management_summary()})


@user_management_bp.get("/roles")
def list_roles():
    engine = _get_user_management_engine()
    roles = [role.to_dict() for role in engine._roles.values()]
    return jsonify({"ok": True, "roles": roles, "count": len(roles)})


@user_management_bp.post("/users")
def create_user():
    engine = _get_user_management_engine()
    payload = request.get_json(silent=True) or {}

    username = str(payload.get("username") or "").strip()
    email = str(payload.get("email") or "").strip()
    password = str(payload.get("password") or "").strip()
    roles = payload.get("roles") or None

    if not username or not email or not password:
        return jsonify({"ok": False, "error": "invalid_request", "message": "username, email and password are required"}), 400

    user_id = engine.create_user(username=username, email=email, password=password, roles=roles)
    return jsonify({"ok": True, "user_id": user_id, "user": engine.get_user(user_id)}), 201


@user_management_bp.post("/users/<user_id>/enable")
def enable_user(user_id: str):
    engine = _get_user_management_engine()
    if not engine.enable_user(user_id):
        return jsonify({"ok": False, "error": "not_found", "user_id": user_id}), 404
    return jsonify({"ok": True, "user_id": user_id, "enabled": True})


@user_management_bp.post("/users/<user_id>/disable")
def disable_user(user_id: str):
    engine = _get_user_management_engine()
    if not engine.disable_user(user_id):
        return jsonify({"ok": False, "error": "not_found", "user_id": user_id}), 404
    return jsonify({"ok": True, "user_id": user_id, "enabled": False})


__all__ = ["user_management_bp"]
