from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wasabi_bp = Blueprint("wasabi", __name__, url_prefix="/api/v1/wasabi")
@wasabi_bp.route("", methods=["GET"])
@require_token
def wasabi(): return jsonify({"ok": True})
