from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rfid_bp = Blueprint("rfid", __name__, url_prefix="/api/v1/rfid")
@rfid_bp.route("", methods=["GET"])
@require_token
def rfid(): return jsonify({"ok": True})
