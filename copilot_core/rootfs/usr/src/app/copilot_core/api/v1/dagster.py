from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dagster_bp = Blueprint("dagster", __name__, url_prefix="/api/v1/dagster")
@dagster_bp.route("", methods=["GET"])
@require_token
def dagster(): return jsonify({"ok": True})
