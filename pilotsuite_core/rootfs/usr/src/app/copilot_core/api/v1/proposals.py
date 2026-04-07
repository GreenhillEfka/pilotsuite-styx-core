"""Proposal lifecycle API.

Blueprint prefix: /api/v1/proposals

Contract (core-side proposal/lifecycle separation):
- Proposals are created by accepting suggestions.
- Execute endpoint materializes proposal into action intent.
- Status endpoints expose the latest canonical lifecycle truth per proposal.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.action_closure import get_action_closure_store
from copilot_core.api.security import require_token
from copilot_core.core.proposal_lifecycle_read_model import (
    build_proposal_lifecycle_status_summary,
    get_proposal_lifecycle_status,
)

_LOGGER = logging.getLogger(__name__)

proposals_bp = Blueprint("proposals", __name__, url_prefix="/api/v1/proposals")

# Module-level service reference, set by init_proposals_api()
_suggestion_engine: Optional[Any] = None


def init_proposals_api(suggestion_engine=None) -> None:
    """Wire suggestion engine and proposal lifecycle methods into this blueprint."""
    global _suggestion_engine
    _suggestion_engine = suggestion_engine
    _LOGGER.info("Proposals API initialized")


def _as_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


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


@proposals_bp.route("", methods=["GET"])
@proposals_bp.route("/api/v1/proposals", methods=["GET"])
def list_proposals():
    """List active proposals."""
    if not _suggestion_engine:
        return jsonify({"ok": True, "count": 0, "proposals": []})

    include_executed = request.args.get("include_executed", "false").lower() in ("1", "true", "yes")
    try:
        proposals = _suggestion_engine.get_proposals(include_executed=include_executed)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "count": len(proposals), "proposals": proposals})


@proposals_bp.route("/<proposal_id>", methods=["GET"])
@proposals_bp.route("/api/v1/proposals/<proposal_id>", methods=["GET"])
def get_proposal(proposal_id: str):
    """Get a proposal by id."""
    if not proposal_id:
        return jsonify({"ok": False, "error": "Missing proposal_id"}), 400

    if not _suggestion_engine:
        return jsonify({"ok": False, "error": "Proposal engine unavailable"}), 503

    proposal = None
    if hasattr(_suggestion_engine, "get_proposal"):
        proposal = _suggestion_engine.get_proposal(proposal_id)

    if proposal is None:
        return jsonify({"ok": False, "error": "Proposal not found"}), 404

    if hasattr(proposal, "to_dict"):
        proposal = proposal.to_dict()

    return jsonify({"ok": True, "proposal": proposal})


@proposals_bp.route("/<proposal_id>/execute", methods=["POST"])
@proposals_bp.route("/api/v1/proposals/<proposal_id>/execute", methods=["POST"])
@require_token
def execute_proposal_endpoint(proposal_id: str):
    """Execute proposal → materialize an action intent."""
    if not proposal_id:
        return jsonify({"ok": False, "error": "Missing proposal_id"}), 400

    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get("dry_run"))

    if not _suggestion_engine:
        return jsonify({"ok": False, "error": "Proposal engine unavailable"}), 503

    method = getattr(_suggestion_engine, "execute_proposal", None)
    if not callable(method):
        return jsonify({"ok": False, "error": "Proposal execute path unavailable"}), 500

    intent = method(proposal_id, dry_run=dry_run)
    if intent is None:
        return jsonify({"ok": False, "error": "Proposal not found"}), 404

    return jsonify({"ok": True, "intent": intent, "dry_run": dry_run})


@proposals_bp.route("/status", methods=["GET"])
@proposals_bp.route("/api/v1/proposals/status", methods=["GET"])
@require_token
def get_proposal_status_summary():
    """Expose the latest canonical lifecycle status per proposal."""
    summary = build_proposal_lifecycle_status_summary(
        get_action_closure_store(),
        proposal_provider=_suggestion_engine,
        proposal_id=_as_text(request.args.get("proposal_id")),
        zone_id=_as_text(request.args.get("zone_id")),
        module_id=_as_text(request.args.get("module_id")),
        lifecycle_status=_as_text(request.args.get("lifecycle_status")),
        recent_limit=_recent_limit(),
        since_revision=_since_revision(),
    )
    return jsonify({"ok": True, "summary": summary.to_dict()})


@proposals_bp.route("/<proposal_id>/status", methods=["GET"])
@proposals_bp.route("/api/v1/proposals/<proposal_id>/status", methods=["GET"])
@require_token
def get_proposal_status(proposal_id: str):
    """Expose the latest canonical lifecycle status for one proposal."""
    if not proposal_id:
        return jsonify({"ok": False, "error": "Missing proposal_id"}), 400

    status = get_proposal_lifecycle_status(
        proposal_id,
        store=get_action_closure_store(),
        proposal_provider=_suggestion_engine,
    )
    if status is None:
        return jsonify({"ok": False, "error": "Proposal status not found"}), 404

    return jsonify({"ok": True, "status": status.to_dict()})
