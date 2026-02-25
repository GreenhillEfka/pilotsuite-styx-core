from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cert_bp = Blueprint("certificate", __name__, url_prefix="/api/v1/certificate")
@cert_bp.route("", methods=["GET"])
@require_token
def cert(): return jsonify({"ok": True})
