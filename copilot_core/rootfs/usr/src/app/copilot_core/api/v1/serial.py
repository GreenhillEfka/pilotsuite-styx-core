from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
serial_bp = Blueprint("serial", __name__, url_prefix="/api/v1/serial")
@serial_bp.route("", methods=["GET"])
@require_token
def serial(): return jsonify({"ok": True})
