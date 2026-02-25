from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mic_bp = Blueprint("mic", __name__, url_prefix="/api/v1/mic")
@mic_bp.route("", methods=["GET"])
@require_token
def mic(): return jsonify({"ok": True})
