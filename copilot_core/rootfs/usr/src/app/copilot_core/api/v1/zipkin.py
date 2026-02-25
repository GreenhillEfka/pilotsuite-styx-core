from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zipkin_bp = Blueprint("zipkin", __name__, url_prefix="/api/v1/zipkin")
@zipkin_bp.route("", methods=["GET"])
@require_token
def zipkin(): return jsonify({"ok": True})
