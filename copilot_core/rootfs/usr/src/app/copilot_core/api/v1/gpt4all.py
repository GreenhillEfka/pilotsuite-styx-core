from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gpt4all_bp = Blueprint("gpt4all", __name__, url_prefix="/api/v1/gpt4all")
@gpt4all_bp.route("", methods=["GET"])
@require_token
def gpt4all(): return jsonify({"ok": True})
