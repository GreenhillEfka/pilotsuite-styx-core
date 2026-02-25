from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
decrypt_bp = Blueprint("decrypt", __name__, url_prefix="/api/v1/decrypt")
@decrypt_bp.route("", methods=["GET"])
@require_token
def decrypt(): return jsonify({"ok": True})
