from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zola_bp = Blueprint("zola", __name__, url_prefix="/api/v1/zola")
@zola_bp.route("", methods=["GET"])
@require_token
def zola(): return jsonify({"ok": True})
