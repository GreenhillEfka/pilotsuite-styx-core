from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
scan_bp = Blueprint("scan", __name__, url_prefix="/api/v1/scan")
@scan_bp.route("", methods=["GET"])
@require_token
def scan(): return jsonify({"ok": True})
