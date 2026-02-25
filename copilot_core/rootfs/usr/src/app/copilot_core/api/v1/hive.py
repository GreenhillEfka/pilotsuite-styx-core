from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hive_bp = Blueprint("hive", __name__, url_prefix="/api/v1/hive")
@hive_bp.route("", methods=["GET"])
@require_token
def hive(): return jsonify({"ok": True})
