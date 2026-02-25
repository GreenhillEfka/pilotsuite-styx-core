from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
insomnia_bp = Blueprint("insomnia", __name__, url_prefix="/api/v1/insomnia")
@insomnia_bp.route("", methods=["GET"])
@require_token
def insomnia(): return jsonify({"ok": True})
