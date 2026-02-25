from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tgi_bp = Blueprint("tgi", __name__, url_prefix="/api/v1/tgi")
@tgi_bp.route("", methods=["GET"])
@require_token
def tgi(): return jsonify({"ok": True})
