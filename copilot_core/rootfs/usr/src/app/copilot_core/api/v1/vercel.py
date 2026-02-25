from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vercel_bp = Blueprint("vercel", __name__, url_prefix="/api/v1/vercel")
@vercel_bp.route("", methods=["GET"])
@require_token
def vercel(): return jsonify({"ok": True})
