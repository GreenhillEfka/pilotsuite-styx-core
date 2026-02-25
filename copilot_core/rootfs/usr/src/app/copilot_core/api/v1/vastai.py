from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vastai_bp = Blueprint("vastai", __name__, url_prefix="/api/v1/vastai")
@vastai_bp.route("", methods=["GET"])
@require_token
def vastai(): return jsonify({"ok": True})
