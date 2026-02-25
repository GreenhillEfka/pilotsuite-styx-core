from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
loki_bp = Blueprint("loki", __name__, url_prefix="/api/v1/loki")
@loki_bp.route("", methods=["GET"])
@require_token
def loki(): return jsonify({"ok": True})
