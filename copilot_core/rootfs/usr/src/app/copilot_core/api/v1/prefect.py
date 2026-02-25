from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
prefect_bp = Blueprint("prefect", __name__, url_prefix="/api/v1/prefect")
@prefect_bp.route("", methods=["GET"])
@require_token
def prefect(): return jsonify({"ok": True})
