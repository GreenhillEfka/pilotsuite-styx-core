from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kind_bp = Blueprint("kind", __name__, url_prefix="/api/v1/kind")
@kind_bp.route("", methods=["GET"])
@require_token
def kind(): return jsonify({"ok": True})
