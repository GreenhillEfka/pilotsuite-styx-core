from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dart_bp = Blueprint("dart", __name__, url_prefix="/api/v1/dart")
@dart_bp.route("", methods=["GET"])
@require_token
def dart(): return jsonify({"ok": True})
