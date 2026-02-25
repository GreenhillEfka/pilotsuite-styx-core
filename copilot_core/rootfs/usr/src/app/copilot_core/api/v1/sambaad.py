from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sambaad_bp = Blueprint("sambaad", __name__, url_prefix="/api/v1/sambaad")
@sambaad_bp.route("", methods=["GET"])
@require_token
def sambaad(): return jsonify({"ok": True})
