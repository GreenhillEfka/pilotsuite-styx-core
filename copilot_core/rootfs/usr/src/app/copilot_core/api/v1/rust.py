from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rust_bp = Blueprint("rust", __name__, url_prefix="/api/v1/rust")
@rust_bp.route("", methods=["GET"])
@require_token
def rust(): return jsonify({"ok": True})
