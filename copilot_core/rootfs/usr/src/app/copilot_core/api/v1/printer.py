from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
printer_bp = Blueprint("printer", __name__, url_prefix="/api/v1/printer")
@printer_bp.route("", methods=["GET"])
@require_token
def printer(): return jsonify({"ok": True})
