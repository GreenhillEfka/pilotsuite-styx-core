from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
test_bp = Blueprint("test", __name__, url_prefix="/api/v1/test")
@test_bp.route("", methods=["GET"])
@require_token
def test(): return jsonify({"ok": True})
