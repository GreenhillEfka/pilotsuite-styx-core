from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pyzor_bp = Blueprint("pyzor", __name__, url_prefix="/api/v1/pyzor")
@pyzor_bp.route("", methods=["GET"])
@require_token
def pyzor(): return jsonify({"ok": True})
