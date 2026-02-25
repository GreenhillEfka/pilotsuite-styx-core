from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
threema_bp = Blueprint("threema", __name__, url_prefix="/api/v1/threema")
@threema_bp.route("", methods=["GET"])
@require_token
def threema(): return jsonify({"ok": True})
