from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
exoscale_bp = Blueprint("exoscale", __name__, url_prefix="/api/v1/exoscale")
@exoscale_bp.route("", methods=["GET"])
@require_token
def exoscale(): return jsonify({"ok": True})
