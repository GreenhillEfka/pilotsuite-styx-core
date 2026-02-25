from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
smtp_bp = Blueprint("smtp", __name__, url_prefix="/api/v1/smtp")
@smtp_bp.route("", methods=["GET"])
@require_token
def smtp(): return jsonify({"ok": True})
