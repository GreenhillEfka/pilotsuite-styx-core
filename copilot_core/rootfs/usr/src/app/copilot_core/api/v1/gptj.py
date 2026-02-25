from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gptj_bp = Blueprint("gptj", __name__, url_prefix="/api/v1/gptj")
@gptj_bp.route("", methods=["GET"])
@require_token
def gptj(): return jsonify({"ok": True})
