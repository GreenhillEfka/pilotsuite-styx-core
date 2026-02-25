from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
awsvpccni_bp = Blueprint("awsvpccni", __name__, url_prefix="/api/v1/awsvpccni")
@awsvpccni_bp.route("", methods=["GET"])
@require_token
def awsvpccni(): return jsonify({"ok": True})
