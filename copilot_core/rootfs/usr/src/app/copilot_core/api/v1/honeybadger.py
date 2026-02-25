from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
honeybadger_bp = Blueprint("honeybadger", __name__, url_prefix="/api/v1/honeybadger")
@honeybadger_bp.route("", methods=["GET"])
@require_token
def honeybadger(): return jsonify({"ok": True})
