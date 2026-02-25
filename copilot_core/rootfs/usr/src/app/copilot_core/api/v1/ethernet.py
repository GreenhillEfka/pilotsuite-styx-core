from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
eth_bp = Blueprint("ethernet", __name__, url_prefix="/api/v1/ethernet")
@eth_bp.route("", methods=["GET"])
@require_token
def ethernet(): return jsonify({"ok": True})
