"""Users API backed by the runtime user-management engine."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.users.engine import UserManagementEngine, create_user_management_engine

users_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")

_USER_ENGINE: UserManagementEngine | None = None


def _get_user_management_engine() -> UserManagementEngine:
    global _USER_ENGINE
    if _USER_ENGINE is None:
        _USER_ENGINE = create_user_management_engine()
    return _USER_ENGINE


@users_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


@users_bp.get("")
def list_users():
    engine = _get_user_management_engine()
    return jsonify({"ok": True, "users": engine.get_all_users(), "count": len(engine.get_all_users())})


@users_bp.get("/<user_id>")
def get_user(user_id: str):
    engine = _get_user_management_engine()
    user = engine.get_user(user_id)
    if user is None:
        return jsonify({"ok": False, "error": "not_found", "user_id": user_id}), 404
    return jsonify({"ok": True, "user": user})


__all__ = ["users_bp", "_get_user_management_engine"]
