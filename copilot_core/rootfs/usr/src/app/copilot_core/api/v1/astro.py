from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
astro_bp = Blueprint("astro", __name__, url_prefix="/api/v1/astro")
@astro_bp.route("", methods=["GET"])
@require_token
def astro(): return jsonify({"ok": True})
