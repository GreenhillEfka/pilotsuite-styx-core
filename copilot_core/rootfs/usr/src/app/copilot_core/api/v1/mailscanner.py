from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mailscanner_bp = Blueprint("mailscanner", __name__, url_prefix="/api/v1/mailscanner")
@mailscanner_bp.route("", methods=["GET"])
@require_token
def mailscanner(): return jsonify({"ok": True})
