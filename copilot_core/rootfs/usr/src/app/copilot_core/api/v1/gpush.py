from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gpush_bp = Blueprint("gpush", __name__, url_prefix="/api/v1/gpush")
@gpush_bp.route("", methods=["GET"])
@require_token
def gpush(): return jsonify({"ok": True})
