from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vbox_bp = Blueprint("vbox", __name__, url_prefix="/api/v1/vbox")
@vbox_bp.route("", methods=["GET"])
@require_token
def vbox(): return jsonify({"ok": True})
