from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
keras_bp = Blueprint("keras", __name__, url_prefix="/api/v1/keras")
@keras_bp.route("", methods=["GET"])
@require_token
def keras(): return jsonify({"ok": True})
