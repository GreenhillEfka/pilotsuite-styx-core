"""Canonical Action Closure API — Slice 17.

Provides one shared feedback / execution-closure surface for proposal-driven
flows across Voice, Predictive, Habitus, and Multi-Zone runtime actions.
"""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.action_closure import get_action_closure_store
from copilot_core.api.security import require_token
from copilot_core.core.action_closure_read_model import (
    build_action_closure_context_block,
    build_action_closure_summary_read_model,
)

action_closure_bp = Blueprint("action_closure", __name__, url_prefix="/api/v1/action-closures")


def _as_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _filters() -> dict[str, str | None]:
    return {
        "source": _as_text(request.args.get("source")),
        "zone_id": _as_text(request.args.get("zone_id")),
        "module_id": _as_text(request.args.get("module_id")),
        "state": _as_text(request.args.get("state")),
        "action_id": _as_text(request.args.get("action_id")),
        "proposal_id": _as_text(request.args.get("proposal_id")),
    }


def _recent_limit(default: int = 5) -> int:
    try:
        return max(1, min(20, int(request.args.get("recent_limit", default))))
    except Exception:
        return default


def _since_revision() -> int | None:
    raw = _as_text(request.args.get("since"))
    if raw is None:
        return None
    try:
        value = int(raw)
    except Exception:
        return None
    return max(0, value)


@action_closure_bp.route("", methods=["GET"])
@require_token
def list_action_closures():
    store = get_action_closure_store()
    closures = store.list(**_filters(), since_revision=_since_revision())
    return jsonify(
        {
            "ok": True,
            "closures": closures,
            "count": len(closures),
            "revision": store.get_current_revision(),
        }
    )


@action_closure_bp.route("/summary", methods=["GET"])
@require_token
def get_action_closure_summary():
    summary = build_action_closure_summary_read_model(
        get_action_closure_store(),
        recent_limit=_recent_limit(),
        since_revision=_since_revision(),
        **_filters(),
    )
    return jsonify({"ok": True, "summary": summary.to_dict()})


@action_closure_bp.route("/context", methods=["GET"])
@require_token
def get_action_closure_context():
    context_block = build_action_closure_context_block(
        get_action_closure_store(),
        recent_limit=_recent_limit(default=3),
        since_revision=_since_revision(),
        **_filters(),
    )
    return jsonify({"ok": True, "context": context_block.to_dict()})


@action_closure_bp.route("/<closure_id>", methods=["GET"])
@require_token
def get_action_closure(closure_id: str):
    store = get_action_closure_store()
    closure = store.get(closure_id)
    if closure is None:
        return jsonify({"ok": False, "error": "closure not found"}), 404
    return jsonify({"ok": True, "closure": closure})


@action_closure_bp.route("/<closure_id>/feedback", methods=["POST"])
@require_token
def record_feedback(closure_id: str):
    payload = request.get_json(silent=True) or {}
    feedback = _as_text(payload.get("feedback"))
    if not feedback:
        return jsonify({"ok": False, "error": "feedback required"}), 400

    store = get_action_closure_store()
    if store.get(closure_id) is None:
        return jsonify({"ok": False, "error": "closure not found"}), 404

    closure = store.record_feedback(
        closure_id,
        feedback=feedback,
        comment=_as_text(payload.get("comment")),
        actor=_as_text(payload.get("actor")) or "user",
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
    )
    return jsonify({"ok": True, "closure": closure})


@action_closure_bp.route("/<closure_id>/execution", methods=["POST"])
@require_token
def record_execution(closure_id: str):
    payload = request.get_json(silent=True) or {}
    outcome = _as_text(payload.get("outcome"))
    if not outcome:
        return jsonify({"ok": False, "error": "outcome required"}), 400

    store = get_action_closure_store()
    if store.get(closure_id) is None:
        return jsonify({"ok": False, "error": "closure not found"}), 404

    closure = store.record_execution(
        closure_id,
        outcome=outcome,
        runtime_source=_as_text(payload.get("runtime_source")) or "runtime.unknown",
        result=payload.get("result") if isinstance(payload.get("result"), dict) else None,
        error=_as_text(payload.get("error")),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        executed_at=_as_text(payload.get("executed_at")),
    )
    return jsonify({"ok": True, "closure": closure})
