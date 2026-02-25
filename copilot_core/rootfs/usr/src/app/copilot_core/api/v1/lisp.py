from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lisp_bp = Blueprint("lisp", __name__, url_prefix="/api/v1/lisp")
@lisp_bp.route("", methods=["GET"])
@require_token
def lisp(): return jsonify({"ok": True})
