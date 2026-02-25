from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bareos_bp = Blueprint("bareos", __name__, url_prefix="/api/v1/bareos")
@bareos_bp.route("", methods=["GET"])
@require_token
def bareos(): return jsonify({"ok": True})
