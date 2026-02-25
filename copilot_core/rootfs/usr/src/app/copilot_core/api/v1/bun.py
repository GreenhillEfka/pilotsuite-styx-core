from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bun_bp = Blueprint("bun", __name__, url_prefix="/api/v1/bun")
@bun_bp.route("", methods=["GET"])
@require_token
def bun(): return jsonify({"ok": True})
