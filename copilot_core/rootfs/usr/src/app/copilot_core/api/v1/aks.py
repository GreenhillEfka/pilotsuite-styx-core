from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
aks_bp = Blueprint("aks", __name__, url_prefix="/api/v1/aks")
@aks_bp.route("", methods=["GET"])
@require_token
def aks(): return jsonify({"ok": True})
