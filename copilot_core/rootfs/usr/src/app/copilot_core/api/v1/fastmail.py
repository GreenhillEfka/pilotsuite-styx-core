from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fastmail_bp = Blueprint("fastmail", __name__, url_prefix="/api/v1/fastmail")
@fastmail_bp.route("", methods=["GET"])
@require_token
def fastmail(): return jsonify({"ok": True})
