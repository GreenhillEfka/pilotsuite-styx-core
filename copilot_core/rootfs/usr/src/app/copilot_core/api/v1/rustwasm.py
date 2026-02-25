from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rustwasm_bp = Blueprint("rustwasm", __name__, url_prefix="/api/v1/rustwasm")
@rustwasm_bp.route("", methods=["GET"])
@require_token
def rustwasm(): return jsonify({"ok": True})
