from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tox_bp = Blueprint("tox", __name__, url_prefix="/api/v1/tox")
@tox_bp.route("", methods=["GET"])
@require_token
def tox(): return jsonify({"ok": True})
