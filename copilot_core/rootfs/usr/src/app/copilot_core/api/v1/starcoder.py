from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
starcoder_bp = Blueprint("starcoder", __name__, url_prefix="/api/v1/starcoder")
@starcoder_bp.route("", methods=["GET"])
@require_token
def starcoder(): return jsonify({"ok": True})
