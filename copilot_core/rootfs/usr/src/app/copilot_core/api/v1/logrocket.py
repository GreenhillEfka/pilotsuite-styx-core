from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
logrocket_bp = Blueprint("logrocket", __name__, url_prefix="/api/v1/logrocket")
@logrocket_bp.route("", methods=["GET"])
@require_token
def logrocket(): return jsonify({"ok": True})
