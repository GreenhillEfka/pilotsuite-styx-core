from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sendmail_bp = Blueprint("sendmail", __name__, url_prefix="/api/v1/sendmail")
@sendmail_bp.route("", methods=["GET"])
@require_token
def sendmail(): return jsonify({"ok": True})
