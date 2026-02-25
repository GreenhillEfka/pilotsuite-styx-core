from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
update_bp = Blueprint("update", __name__, url_prefix="/api/v1/update")
@update_bp.route("", methods=["GET"])
@require_token
def update(): return jsonify({"ok": True})
