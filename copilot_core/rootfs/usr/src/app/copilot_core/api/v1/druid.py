from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
druid_bp = Blueprint("druid", __name__, url_prefix="/api/v1/druid")
@druid_bp.route("", methods=["GET"])
@require_token
def druid(): return jsonify({"ok": True})
