from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dreamobjects_bp = Blueprint("dreamobjects", __name__, url_prefix="/api/v1/dreamobjects")
@dreamobjects_bp.route("", methods=["GET"])
@require_token
def dreamobjects(): return jsonify({"ok": True})
