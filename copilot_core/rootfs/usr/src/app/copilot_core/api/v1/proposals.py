"""Proposal lifecycle API.

Blueprint prefix: /api/v1/proposals

Contract (core-side proposal/lifecycle separation):
- Proposals are created by accepting suggestions.
- Execute endpoint materializes proposal into action intent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

proposals_bp = Blueprint("proposals", __name__)

# Module-level service reference, set by init_proposals_api()
_suggestion_engine: Optional[Any] = None


def init_proposals_api(suggestion_engine=None) -> None:
    """Wire suggestion engine and proposal lifecycle methods into this blueprint."""
    global _suggestion_engine
    _suggestion_engine = suggestion_engine
    _LOGGER.info("Proposals API initialized")


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

    return jsonify({"ok": True, "proposal": proposal})


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
