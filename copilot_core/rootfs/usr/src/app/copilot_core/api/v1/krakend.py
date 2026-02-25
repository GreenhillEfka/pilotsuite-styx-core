from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
krakend_bp = Blueprint("krakend", __name__, url_prefix="/api/v1/krakend")
@krakend_bp.route("", methods=["GET"])
@require_token
def krakend(): return jsonify({"ok": True})
