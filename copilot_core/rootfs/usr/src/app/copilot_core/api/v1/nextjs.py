from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nextjs_bp = Blueprint("nextjs", __name__, url_prefix="/api/v1/nextjs")
@nextjs_bp.route("", methods=["GET"])
@require_token
def nextjs(): return jsonify({"ok": True})
