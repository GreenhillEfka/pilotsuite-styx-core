from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
heap_bp = Blueprint("heap", __name__, url_prefix="/api/v1/heap")
@heap_bp.route("", methods=["GET"])
@require_token
def heap(): return jsonify({"ok": True})
