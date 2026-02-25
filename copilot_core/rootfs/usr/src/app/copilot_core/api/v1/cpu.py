from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cpu_bp = Blueprint("cpu", __name__, url_prefix="/api/v1/cpu")
@cpu_bp.route("", methods=["GET"])
@require_token
def cpu(): return jsonify({"ok": True})
