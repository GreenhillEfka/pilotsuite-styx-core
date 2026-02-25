from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
spinnaker_bp = Blueprint("spinnaker", __name__, url_prefix="/api/v1/spinnaker")
@spinnaker_bp.route("", methods=["GET"])
@require_token
def spinnaker(): return jsonify({"ok": True})
