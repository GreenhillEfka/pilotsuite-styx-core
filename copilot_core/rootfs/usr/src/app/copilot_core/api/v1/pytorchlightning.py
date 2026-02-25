from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pytorchlightning_bp = Blueprint("pytorchlightning", __name__, url_prefix="/api/v1/pytorchlightning")
@pytorchlightning_bp.route("", methods=["GET"])
@require_token
def pytorchlightning(): return jsonify({"ok": True})
