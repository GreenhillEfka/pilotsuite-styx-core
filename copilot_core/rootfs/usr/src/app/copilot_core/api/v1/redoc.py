from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
redoc_bp = Blueprint("redoc", __name__, url_prefix="/api/v1/redoc")
@redoc_bp.route("", methods=["GET"])
@require_token
def redoc(): return jsonify({"ok": True})
