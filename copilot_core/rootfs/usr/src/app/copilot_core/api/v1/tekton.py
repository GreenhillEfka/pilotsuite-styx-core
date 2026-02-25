from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tekton_bp = Blueprint("tekton", __name__, url_prefix="/api/v1/tekton")
@tekton_bp.route("", methods=["GET"])
@require_token
def tekton(): return jsonify({"ok": True})
