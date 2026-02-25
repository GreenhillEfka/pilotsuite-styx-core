from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
spacewalk_bp = Blueprint("spacewalk", __name__, url_prefix="/api/v1/spacewalk")
@spacewalk_bp.route("", methods=["GET"])
@require_token
def spacewalk(): return jsonify({"ok": True})
