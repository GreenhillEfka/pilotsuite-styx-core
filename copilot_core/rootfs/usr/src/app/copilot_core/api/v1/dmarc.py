from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dmarc_bp = Blueprint("dmarc", __name__, url_prefix="/api/v1/dmarc")
@dmarc_bp.route("", methods=["GET"])
@require_token
def dmarc(): return jsonify({"ok": True})
