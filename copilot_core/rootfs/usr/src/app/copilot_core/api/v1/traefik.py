from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
traefik_bp = Blueprint("traefik", __name__, url_prefix="/api/v1/traefik")
@traefik_bp.route("", methods=["GET"])
@require_token
def traefik(): return jsonify({"ok": True})
