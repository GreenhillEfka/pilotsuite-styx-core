from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rdp3_bp = Blueprint("rdp3", __name__, url_prefix="/api/v1/rdp3")
@rdp3_bp.route("", methods=["GET"])
@require_token
def rdp3(): return jsonify({"ok": True})
