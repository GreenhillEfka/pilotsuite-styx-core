from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
awq_bp = Blueprint("awq", __name__, url_prefix="/api/v1/awq")
@awq_bp.route("", methods=["GET"])
@require_token
def awq(): return jsonify({"ok": True})
