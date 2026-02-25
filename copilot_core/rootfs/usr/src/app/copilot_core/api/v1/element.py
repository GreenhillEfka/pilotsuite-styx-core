from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
element_bp = Blueprint("element", __name__, url_prefix="/api/v1/element")
@element_bp.route("", methods=["GET"])
@require_token
def element(): return jsonify({"ok": True})
