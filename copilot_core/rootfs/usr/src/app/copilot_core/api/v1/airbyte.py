from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
airbyte_bp = Blueprint("airbyte", __name__, url_prefix="/api/v1/airbyte")
@airbyte_bp.route("", methods=["GET"])
@require_token
def airbyte(): return jsonify({"ok": True})
