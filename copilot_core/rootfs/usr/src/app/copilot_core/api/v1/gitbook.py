from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gitbook_bp = Blueprint("gitbook", __name__, url_prefix="/api/v1/gitbook")
@gitbook_bp.route("", methods=["GET"])
@require_token
def gitbook(): return jsonify({"ok": True})
