from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
codegen_bp = Blueprint("codegen", __name__, url_prefix="/api/v1/codegen")
@codegen_bp.route("", methods=["GET"])
@require_token
def codegen(): return jsonify({"ok": True})
