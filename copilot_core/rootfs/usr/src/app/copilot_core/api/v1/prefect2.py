from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
prefect2_bp = Blueprint("prefect2", __name__, url_prefix="/api/v1/prefect2")
@prefect2_bp.route("", methods=["GET"])
@require_token
def prefect2(): return jsonify({"ok": True})
