from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
caddy_bp = Blueprint("caddy", __name__, url_prefix="/api/v1/caddy")
@caddy_bp.route("", methods=["GET"])
@require_token
def caddy(): return jsonify({"ok": True})
