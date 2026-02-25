from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
esxi_bp = Blueprint("esxi", __name__, url_prefix="/api/v1/esxi")
@esxi_bp.route("", methods=["GET"])
@require_token
def esxi(): return jsonify({"ok": True})
