from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
clojure_bp = Blueprint("clojure", __name__, url_prefix="/api/v1/clojure")
@clojure_bp.route("", methods=["GET"])
@require_token
def clojure(): return jsonify({"ok": True})
