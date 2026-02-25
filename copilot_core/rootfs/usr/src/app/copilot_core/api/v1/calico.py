from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
calico_bp = Blueprint("calico", __name__, url_prefix="/api/v1/calico")
@calico_bp.route("", methods=["GET"])
@require_token
def calico(): return jsonify({"ok": True})
