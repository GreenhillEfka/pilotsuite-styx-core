from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
matter_bp = Blueprint("matter", __name__, url_prefix="/api/v1/matter")
@matter_bp.route("", methods=["GET"])
@require_token
def matter(): return jsonify({"ok": True})
