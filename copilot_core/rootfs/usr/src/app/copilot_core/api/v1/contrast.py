from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
contrast_bp = Blueprint("contrast", __name__, url_prefix="/api/v1/contrast")
@contrast_bp.route("", methods=["GET"])
@require_token
def contrast(): return jsonify({"ok": True})
