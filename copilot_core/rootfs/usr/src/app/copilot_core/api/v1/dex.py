from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dex_bp = Blueprint("dex", __name__, url_prefix="/api/v1/dex")
@dex_bp.route("", methods=["GET"])
@require_token
def dex(): return jsonify({"ok": True})
