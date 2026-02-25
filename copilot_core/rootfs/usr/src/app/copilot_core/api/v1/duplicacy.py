from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
duplicacy_bp = Blueprint("duplicacy", __name__, url_prefix="/api/v1/duplicacy")
@duplicacy_bp.route("", methods=["GET"])
@require_token
def duplicacy(): return jsonify({"ok": True})
