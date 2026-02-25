from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
davmail_bp = Blueprint("davmail", __name__, url_prefix="/api/v1/davmail")
@davmail_bp.route("", methods=["GET"])
@require_token
def davmail(): return jsonify({"ok": True})
