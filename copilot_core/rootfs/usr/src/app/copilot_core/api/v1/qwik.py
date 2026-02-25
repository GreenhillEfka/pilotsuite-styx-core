from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
qwik_bp = Blueprint("qwik", __name__, url_prefix="/api/v1/qwik")
@qwik_bp.route("", methods=["GET"])
@require_token
def qwik(): return jsonify({"ok": True})
