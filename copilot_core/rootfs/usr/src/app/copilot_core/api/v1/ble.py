from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ble_bp = Blueprint("ble", __name__, url_prefix="/api/v1/ble")
@ble_bp.route("", methods=["GET"])
@require_token
def ble(): return jsonify({"ok": True})
