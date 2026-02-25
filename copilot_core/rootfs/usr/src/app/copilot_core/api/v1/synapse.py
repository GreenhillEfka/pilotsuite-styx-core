from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
synapse_bp = Blueprint("synapse", __name__, url_prefix="/api/v1/synapse")
@synapse_bp.route("", methods=["GET"])
@require_token
def synapse(): return jsonify({"ok": True})
