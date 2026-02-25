from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
temporal_bp = Blueprint("temporal", __name__, url_prefix="/api/v1/temporal")
@temporal_bp.route("", methods=["GET"])
@require_token
def temporal(): return jsonify({"ok": True})
