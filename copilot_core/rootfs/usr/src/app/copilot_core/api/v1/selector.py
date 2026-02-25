from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
selector_bp = Blueprint("selector", __name__, url_prefix="/api/v1/selector")
@selector_bp.route("", methods=["GET"])
@require_token
def selector(): return jsonify({"ok": True})
