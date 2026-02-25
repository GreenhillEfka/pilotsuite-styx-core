from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
llamaindex_bp = Blueprint("llamaindex", __name__, url_prefix="/api/v1/llamaindex")
@llamaindex_bp.route("", methods=["GET"])
@require_token
def llamaindex(): return jsonify({"ok": True})
