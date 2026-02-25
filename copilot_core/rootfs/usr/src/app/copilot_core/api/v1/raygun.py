from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
raygun_bp = Blueprint("raygun", __name__, url_prefix="/api/v1/raygun")
@raygun_bp.route("", methods=["GET"])
@require_token
def raygun(): return jsonify({"ok": True})
