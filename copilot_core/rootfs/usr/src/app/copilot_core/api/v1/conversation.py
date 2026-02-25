"""Conversation API endpoints for PilotSuite Styx."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

conversation_bp = Blueprint("conversation", __name__, url_prefix="/api/v1/conversation")


def normalize_requested_model(requested: str) -> str:
    """Normalize user-facing model aliases to internal selectors.
    
    mapping:
      - "pilotsuite" / "default" / "auto" / "" / "primary" → "primary"
      - "local" / "offline" / "ollama" → "offline"
      - "cloud" / "remote" → "cloud"
      - everything else → preserved as-is (explicit model name)
    """
    value = str(requested or "").strip().lower()
    if not value or value in {"pilotsuite", "default", "auto", "primary"}:
        return "primary"
    if value in {"local", "offline", "ollama"}:
        return "offline"
    if value in {"cloud", "remote"}:
        return "cloud"
    return requested.strip()


@conversation_bp.route("", methods=["GET"])
@require_token
def conversation() -> tuple[str, int]:
    """Health check for conversation endpoint."""
    return jsonify({"ok": True}), 200


@conversation_bp.route("/normalize", methods=["POST"])
@require_token
def normalize_model() -> tuple[str, int]:
    """Normalize a requested model name to internal selector."""
    body = request.get_json(silent=True) or {}
    requested = str(body.get("model", "") or "").strip()
    normalized = normalize_requested_model(requested)
    return jsonify({
        "ok": True,
        "requested": requested,
        "normalized": normalized,
    }), 200
