from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
plausible_bp = Blueprint("plausible", __name__, url_prefix="/api/v1/plausible")
@plausible_bp.route("", methods=["GET"])
@require_token
def plausible(): return jsonify({"ok": True})
