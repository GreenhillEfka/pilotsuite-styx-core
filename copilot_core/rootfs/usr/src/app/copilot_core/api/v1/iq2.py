from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
iq2_bp = Blueprint("iq2", __name__, url_prefix="/api/v1/iq2")
@iq2_bp.route("", methods=["GET"])
@require_token
def iq2(): return jsonify({"ok": True})
