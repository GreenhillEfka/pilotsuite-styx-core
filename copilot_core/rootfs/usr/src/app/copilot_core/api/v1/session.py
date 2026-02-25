from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
session_bp = Blueprint("session", __name__, url_prefix="/api/v1/session")
@session_bp.route("", methods=["GET"])
@require_token
def session(): return jsonify({"ok": True})
