from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lte_bp = Blueprint("lte", __name__, url_prefix="/api/v1/lte")
@lte_bp.route("", methods=["GET"])
@require_token
def lte(): return jsonify({"ok": True})
