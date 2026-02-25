from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
annoy_bp = Blueprint("annoy", __name__, url_prefix="/api/v1/annoy")
@annoy_bp.route("", methods=["GET"])
@require_token
def annoy(): return jsonify({"ok": True})
