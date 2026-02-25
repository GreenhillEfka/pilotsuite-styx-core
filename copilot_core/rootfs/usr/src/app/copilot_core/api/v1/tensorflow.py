from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tensorflow_bp = Blueprint("tensorflow", __name__, url_prefix="/api/v1/tensorflow")
@tensorflow_bp.route("", methods=["GET"])
@require_token
def tensorflow(): return jsonify({"ok": True})
