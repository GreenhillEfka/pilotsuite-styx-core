from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nikola_bp = Blueprint("nikola", __name__, url_prefix="/api/v1/nikola")
@nikola_bp.route("", methods=["GET"])
@require_token
def nikola(): return jsonify({"ok": True})
