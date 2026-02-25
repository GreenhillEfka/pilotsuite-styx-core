from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rspamd_bp = Blueprint("rspamd", __name__, url_prefix="/api/v1/rspamd")
@rspamd_bp.route("", methods=["GET"])
@require_token
def rspamd(): return jsonify({"ok": True})
