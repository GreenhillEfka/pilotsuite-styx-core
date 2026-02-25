from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
scanner_bp = Blueprint("scanner", __name__, url_prefix="/api/v1/scanner")
@scanner_bp.route("", methods=["GET"])
@require_token
def scanner(): return jsonify({"ok": True})
