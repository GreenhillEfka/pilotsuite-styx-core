from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
helm_bp = Blueprint("helm", __name__, url_prefix="/api/v1/helm")
@helm_bp.route("", methods=["GET"])
@require_token
def helm(): return jsonify({"ok": True})
