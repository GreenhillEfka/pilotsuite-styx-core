from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
istio_bp = Blueprint("istio", __name__, url_prefix="/api/v1/istio")
@istio_bp.route("", methods=["GET"])
@require_token
def istio(): return jsonify({"ok": True})
