from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
keycloak_bp = Blueprint("keycloak", __name__, url_prefix="/api/v1/keycloak")
@keycloak_bp.route("", methods=["GET"])
@require_token
def keycloak(): return jsonify({"ok": True})
