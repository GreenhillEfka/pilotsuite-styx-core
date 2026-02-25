from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
devspace_bp = Blueprint("devspace", __name__, url_prefix="/api/v1/devspace")
@devspace_bp.route("", methods=["GET"])
@require_token
def devspace(): return jsonify({"ok": True})
