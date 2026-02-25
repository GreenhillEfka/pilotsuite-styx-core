from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zpush_bp = Blueprint("zpush", __name__, url_prefix="/api/v1/zpush")
@zpush_bp.route("", methods=["GET"])
@require_token
def zpush(): return jsonify({"ok": True})
