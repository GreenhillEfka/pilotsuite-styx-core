from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nfc_bp = Blueprint("nfc", __name__, url_prefix="/api/v1/nfc")
@nfc_bp.route("", methods=["GET"])
@require_token
def nfc(): return jsonify({"ok": True})
