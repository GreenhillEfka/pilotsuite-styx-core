from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
microk8s_bp = Blueprint("microk8s", __name__, url_prefix="/api/v1/microk8s")
@microk8s_bp.route("", methods=["GET"])
@require_token
def microk8s(): return jsonify({"ok": True})
