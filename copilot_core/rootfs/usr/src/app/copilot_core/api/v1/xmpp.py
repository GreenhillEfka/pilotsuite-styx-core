from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
xmpp_bp = Blueprint("xmpp", __name__, url_prefix="/api/v1/xmpp")
@xmpp_bp.route("", methods=["GET"])
@require_token
def xmpp(): return jsonify({"ok": True})
