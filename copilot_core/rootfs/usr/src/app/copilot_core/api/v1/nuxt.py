from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nuxt_bp = Blueprint("nuxt", __name__, url_prefix="/api/v1/nuxt")
@nuxt_bp.route("", methods=["GET"])
@require_token
def nuxt(): return jsonify({"ok": True})
