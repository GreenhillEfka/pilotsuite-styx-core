from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cockpit_bp = Blueprint("cockpit", __name__, url_prefix="/api/v1/cockpit")
@cockpit_bp.route("", methods=["GET"])
@require_token
def cockpit(): return jsonify({"ok": True})
