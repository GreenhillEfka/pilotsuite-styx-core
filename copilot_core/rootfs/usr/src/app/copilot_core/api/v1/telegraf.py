from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
telegraf_bp = Blueprint("telegraf", __name__, url_prefix="/api/v1/telegraf")
@telegraf_bp.route("", methods=["GET"])
@require_token
def telegraf(): return jsonify({"ok": True})
