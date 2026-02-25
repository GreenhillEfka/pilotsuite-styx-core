from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
shop_bp = Blueprint("shop", __name__, url_prefix="/api/v1/shop")
@shop_bp.route("", methods=["GET"])
@require_token
def shop(): return jsonify({"ok": True})
