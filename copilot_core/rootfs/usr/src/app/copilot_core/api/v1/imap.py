from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
imap_bp = Blueprint("imap", __name__, url_prefix="/api/v1/imap")
@imap_bp.route("", methods=["GET"])
@require_token
def imap(): return jsonify({"ok": True})
