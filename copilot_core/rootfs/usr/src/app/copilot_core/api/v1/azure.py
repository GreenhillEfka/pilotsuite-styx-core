from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
azure_bp = Blueprint("azure", __name__, url_prefix="/api/v1/azure")
@azure_bp.route("", methods=["GET"])
@require_token
def azure(): return jsonify({"ok": True})
