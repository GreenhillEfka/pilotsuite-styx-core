from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
matter12_bp = Blueprint("matter12", __name__, url_prefix="/api/v1/matter12")
@matter12_bp.route("", methods=["GET"])
@require_token
def matter12(): return jsonify({"ok": True})
