from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
matter13_bp = Blueprint("matter13", __name__, url_prefix="/api/v1/matter13")
@matter13_bp.route("", methods=["GET"])
@require_token
def matter13(): return jsonify({"ok": True})
