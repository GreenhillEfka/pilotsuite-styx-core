from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
envoy_bp = Blueprint("envoy", __name__, url_prefix="/api/v1/envoy")
@envoy_bp.route("", methods=["GET"])
@require_token
def envoy(): return jsonify({"ok": True})
