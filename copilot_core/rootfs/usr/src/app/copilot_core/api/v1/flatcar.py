from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
flatcar_bp = Blueprint("flatcar", __name__, url_prefix="/api/v1/flatcar")
@flatcar_bp.route("", methods=["GET"])
@require_token
def flatcar(): return jsonify({"ok": True})
