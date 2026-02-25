from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
modem_bp = Blueprint("modem", __name__, url_prefix="/api/v1/modem")
@modem_bp.route("", methods=["GET"])
@require_token
def modem(): return jsonify({"ok": True})
