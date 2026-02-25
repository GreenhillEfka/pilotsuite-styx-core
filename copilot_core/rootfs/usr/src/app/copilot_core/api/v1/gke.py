from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gke_bp = Blueprint("gke", __name__, url_prefix="/api/v1/gke")
@gke_bp.route("", methods=["GET"])
@require_token
def gke(): return jsonify({"ok": True})
