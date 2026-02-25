from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cloudstack_bp = Blueprint("cloudstack", __name__, url_prefix="/api/v1/cloudstack")
@cloudstack_bp.route("", methods=["GET"])
@require_token
def cloudstack(): return jsonify({"ok": True})
