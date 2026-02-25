from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
metallb_bp = Blueprint("metallb", __name__, url_prefix="/api/v1/metallb")
@metallb_bp.route("", methods=["GET"])
@require_token
def metallb(): return jsonify({"ok": True})
