from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dagster2_bp = Blueprint("dagster2", __name__, url_prefix="/api/v1/dagster2")
@dagster2_bp.route("", methods=["GET"])
@require_token
def dagster2(): return jsonify({"ok": True})
