from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
scann_bp = Blueprint("scann", __name__, url_prefix="/api/v1/scann")
@scann_bp.route("", methods=["GET"])
@require_token
def scann(): return jsonify({"ok": True})
