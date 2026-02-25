from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
writeas_bp = Blueprint("writeas", __name__, url_prefix="/api/v1/writeas")
@writeas_bp.route("", methods=["GET"])
@require_token
def writeas(): return jsonify({"ok": True})
