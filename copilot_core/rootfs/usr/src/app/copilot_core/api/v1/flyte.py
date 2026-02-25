from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
flyte_bp = Blueprint("flyte", __name__, url_prefix="/api/v1/flyte")
@flyte_bp.route("", methods=["GET"])
@require_token
def flyte(): return jsonify({"ok": True})
