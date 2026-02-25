from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
skaffold_bp = Blueprint("skaffold", __name__, url_prefix="/api/v1/skaffold")
@skaffold_bp.route("", methods=["GET"])
@require_token
def skaffold(): return jsonify({"ok": True})
