from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
typescript_bp = Blueprint("typescript", __name__, url_prefix="/api/v1/typescript")
@typescript_bp.route("", methods=["GET"])
@require_token
def typescript(): return jsonify({"ok": True})
