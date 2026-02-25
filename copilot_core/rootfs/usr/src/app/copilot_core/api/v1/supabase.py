from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
supabase_bp = Blueprint("supabase", __name__, url_prefix="/api/v1/supabase")
@supabase_bp.route("", methods=["GET"])
@require_token
def supabase(): return jsonify({"ok": True})
