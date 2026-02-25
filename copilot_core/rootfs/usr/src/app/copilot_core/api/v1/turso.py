from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
turso_bp = Blueprint("turso", __name__, url_prefix="/api/v1/turso")
@turso_bp.route("", methods=["GET"])
@require_token
def turso(): return jsonify({"ok": True})
