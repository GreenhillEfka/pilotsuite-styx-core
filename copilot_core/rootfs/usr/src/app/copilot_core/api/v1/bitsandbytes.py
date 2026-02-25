from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bitsandbytes_bp = Blueprint("bitsandbytes", __name__, url_prefix="/api/v1/bitsandbytes")
@bitsandbytes_bp.route("", methods=["GET"])
@require_token
def bitsandbytes(): return jsonify({"ok": True})
