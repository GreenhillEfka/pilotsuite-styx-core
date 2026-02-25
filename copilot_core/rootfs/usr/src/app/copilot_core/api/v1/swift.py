from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
swift_bp = Blueprint("swift", __name__, url_prefix="/api/v1/swift")
@swift_bp.route("", methods=["GET"])
@require_token
def swift(): return jsonify({"ok": True})
