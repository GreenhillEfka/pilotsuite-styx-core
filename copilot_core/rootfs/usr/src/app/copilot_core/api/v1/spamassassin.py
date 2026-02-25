from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
spamassassin_bp = Blueprint("spamassassin", __name__, url_prefix="/api/v1/spamassassin")
@spamassassin_bp.route("", methods=["GET"])
@require_token
def spamassassin(): return jsonify({"ok": True})
