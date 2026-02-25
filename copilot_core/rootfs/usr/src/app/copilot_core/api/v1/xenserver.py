from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
xenserver_bp = Blueprint("xenserver", __name__, url_prefix="/api/v1/xenserver")
@xenserver_bp.route("", methods=["GET"])
@require_token
def xenserver(): return jsonify({"ok": True})
