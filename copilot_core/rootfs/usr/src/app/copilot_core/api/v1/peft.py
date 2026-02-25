from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
peft_bp = Blueprint("peft", __name__, url_prefix="/api/v1/peft")
@peft_bp.route("", methods=["GET"])
@require_token
def peft(): return jsonify({"ok": True})
