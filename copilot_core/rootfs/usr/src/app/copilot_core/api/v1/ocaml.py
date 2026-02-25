from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ocaml_bp = Blueprint("ocaml", __name__, url_prefix="/api/v1/ocaml")
@ocaml_bp.route("", methods=["GET"])
@require_token
def ocaml(): return jsonify({"ok": True})
