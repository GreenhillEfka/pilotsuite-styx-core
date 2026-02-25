from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lmstudio_bp = Blueprint("lmstudio", __name__, url_prefix="/api/v1/lmstudio")
@lmstudio_bp.route("", methods=["GET"])
@require_token
def lmstudio(): return jsonify({"ok": True})
