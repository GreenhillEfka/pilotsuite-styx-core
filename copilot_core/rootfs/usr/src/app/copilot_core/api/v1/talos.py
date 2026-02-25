from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
talos_bp = Blueprint("talos", __name__, url_prefix="/api/v1/talos")
@talos_bp.route("", methods=["GET"])
@require_token
def talos(): return jsonify({"ok": True})
