from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lora_bp = Blueprint("lora", __name__, url_prefix="/api/v1/lora")
@lora_bp.route("", methods=["GET"])
@require_token
def lora(): return jsonify({"ok": True})
