from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
water_bp = Blueprint("water", __name__, url_prefix="/api/v1/water_heater")
@water_bp.route("", methods=["GET"])
@require_token
def water(): return jsonify({"ok": True})
