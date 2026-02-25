from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
runpod_bp = Blueprint("runpod", __name__, url_prefix="/api/v1/runpod")
@runpod_bp.route("", methods=["GET"])
@require_token
def runpod(): return jsonify({"ok": True})
