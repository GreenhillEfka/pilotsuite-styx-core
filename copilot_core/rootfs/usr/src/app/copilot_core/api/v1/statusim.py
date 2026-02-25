from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
status_bp = Blueprint("status", __name__, url_prefix="/api/v1/statusim")
@status_bp.route("", methods=["GET"])
@require_token
def statusim(): return jsonify({"ok": True})
