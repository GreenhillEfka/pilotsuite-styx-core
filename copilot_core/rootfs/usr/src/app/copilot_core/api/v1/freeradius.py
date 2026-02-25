from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
freeradius_bp = Blueprint("freeradius", __name__, url_prefix="/api/v1/freeradius")
@freeradius_bp.route("", methods=["GET"])
@require_token
def freeradius(): return jsonify({"ok": True})
