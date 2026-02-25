from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
motel_bp = Blueprint("motel", __name__, url_prefix="/api/v1/motel")
@motel_bp.route("", methods=["GET"])
@require_token
def motel(): return jsonify({"ok": True})
