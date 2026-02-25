from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ruby_bp = Blueprint("ruby", __name__, url_prefix="/api/v1/ruby")
@ruby_bp.route("", methods=["GET"])
@require_token
def ruby(): return jsonify({"ok": True})
