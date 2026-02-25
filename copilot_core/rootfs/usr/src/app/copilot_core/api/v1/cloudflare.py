from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cloudflare_bp = Blueprint("cloudflare", __name__, url_prefix="/api/v1/cloudflare")
@cloudflare_bp.route("", methods=["GET"])
@require_token
def cloudflare(): return jsonify({"ok": True})
