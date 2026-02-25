from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ovh_bp = Blueprint("ovh", __name__, url_prefix="/api/v1/ovh")
@ovh_bp.route("", methods=["GET"])
@require_token
def ovh(): return jsonify({"ok": True})
