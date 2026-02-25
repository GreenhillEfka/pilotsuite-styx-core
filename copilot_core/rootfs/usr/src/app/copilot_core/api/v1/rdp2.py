from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rdp2_bp = Blueprint("rdp2", __name__, url_prefix="/api/v1/rdp2")
@rdp2_bp.route("", methods=["GET"])
@require_token
def rdp2(): return jsonify({"ok": True})
