from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zulip_bp = Blueprint("zulip", __name__, url_prefix="/api/v1/zulip")
@zulip_bp.route("", methods=["GET"])
@require_token
def zulip(): return jsonify({"ok": True})
