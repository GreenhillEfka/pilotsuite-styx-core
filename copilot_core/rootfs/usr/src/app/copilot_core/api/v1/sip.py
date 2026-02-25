from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sip_bp = Blueprint("sip", __name__, url_prefix="/api/v1/sip")
@sip_bp.route("", methods=["GET"])
@require_token
def sip(): return jsonify({"ok": True})
