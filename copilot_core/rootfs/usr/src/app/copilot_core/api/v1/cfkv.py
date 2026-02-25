from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cfkv_bp = Blueprint("cfkv", __name__, url_prefix="/api/v1/cfkv")
@cfkv_bp.route("", methods=["GET"])
@require_token
def cfkv(): return jsonify({"ok": True})
