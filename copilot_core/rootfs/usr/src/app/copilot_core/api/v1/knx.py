from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
knx_bp = Blueprint("knx", __name__, url_prefix="/api/v1/knx")
@knx_bp.route("", methods=["GET"])
@require_token
def knx(): return jsonify({"ok": True})
