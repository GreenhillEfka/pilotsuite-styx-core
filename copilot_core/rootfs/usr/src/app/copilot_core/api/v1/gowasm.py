from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gowasm_bp = Blueprint("gowasm", __name__, url_prefix="/api/v1/gowasm")
@gowasm_bp.route("", methods=["GET"])
@require_token
def gowasm(): return jsonify({"ok": True})
