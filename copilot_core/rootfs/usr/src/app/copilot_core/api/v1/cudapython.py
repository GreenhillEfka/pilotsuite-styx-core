from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cudapython_bp = Blueprint("cudapython", __name__, url_prefix="/api/v1/cudapython")
@cudapython_bp.route("", methods=["GET"])
@require_token
def cudapython(): return jsonify({"ok": True})
