from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wakeword_bp = Blueprint("wakeword", __name__, url_prefix="/api/v1/wakeword")
@wakeword_bp.route("", methods=["GET"])
@require_token
def wakeword(): return jsonify({"ok": True})
