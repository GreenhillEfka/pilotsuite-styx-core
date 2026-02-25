from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
qlora_bp = Blueprint("qlora", __name__, url_prefix="/api/v1/qlora")
@qlora_bp.route("", methods=["GET"])
@require_token
def qlora(): return jsonify({"ok": True})
