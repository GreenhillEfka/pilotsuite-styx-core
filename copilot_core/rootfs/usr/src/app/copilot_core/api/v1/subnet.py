from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
subnet_bp = Blueprint("subnet", __name__, url_prefix="/api/v1/subnet")
@subnet_bp.route("", methods=["GET"])
@require_token
def subnet(): return jsonify({"ok": True})
