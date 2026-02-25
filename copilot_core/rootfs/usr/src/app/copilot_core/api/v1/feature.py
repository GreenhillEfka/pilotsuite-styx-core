from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
feature_bp = Blueprint("feature", __name__, url_prefix="/api/v1/feature")
@feature_bp.route("", methods=["GET"])
@require_token
def feature(): return jsonify({"ok": True})
