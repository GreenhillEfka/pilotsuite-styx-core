from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ovh2_bp = Blueprint("ovh2", __name__, url_prefix="/api/v1/ovh2")
@ovh2_bp.route("", methods=["GET"])
@require_token
def ovh2(): return jsonify({"ok": True})
