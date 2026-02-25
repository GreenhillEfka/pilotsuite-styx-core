from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vpn_bp = Blueprint("vpn", __name__, url_prefix="/api/v1/vpn")
@vpn_bp.route("", methods=["GET"])
@require_token
def vpn(): return jsonify({"ok": True})
