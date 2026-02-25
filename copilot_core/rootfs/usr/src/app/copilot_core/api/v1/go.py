from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
go_bp = Blueprint("go", __name__, url_prefix="/api/v1/go")
@go_bp.route("", methods=["GET"])
@require_token
def go(): return jsonify({"ok": True})
