from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
extdns_bp = Blueprint("extdns", __name__, url_prefix="/api/v1/extdns")
@extdns_bp.route("", methods=["GET"])
@require_token
def extdns(): return jsonify({"ok": True})
