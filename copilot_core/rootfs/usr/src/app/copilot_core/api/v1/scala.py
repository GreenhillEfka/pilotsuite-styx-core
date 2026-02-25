from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
scala_bp = Blueprint("scala", __name__, url_prefix="/api/v1/scala")
@scala_bp.route("", methods=["GET"])
@require_token
def scala(): return jsonify({"ok": True})
