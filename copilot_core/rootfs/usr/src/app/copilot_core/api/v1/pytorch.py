from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pytorch_bp = Blueprint("pytorch", __name__, url_prefix="/api/v1/pytorch")
@pytorch_bp.route("", methods=["GET"])
@require_token
def pytorch(): return jsonify({"ok": True})
