"""Proposal Follow-Up Claim / Lease API for Slice 38.

Enables workers to claim proposal follow-ups with lease expiry, reassign visibility,
and settlement without building a second worker lock logic.
"""
from __future__ import annotations

from typing import Any
from flask import Blueprint, jsonify, request

from copilot_core.core.proposal_follow_up_claim import (
    get_proposal_follow_up_claim_store,
)


proposal_claims_bp = Blueprint("proposal_claims", __name__, url_prefix="/notifications/proposals")


@proposal_claims_bp.route("/dispatch/claim", methods=["POST"])
def claim_dispatch() -> tuple[Any, int]:
    """Claim a proposal follow-up dispatch candidate.
    
    Request body:
    {
        "dispatch_id": "string",
        "proposal_id": "string",
        "worker_id": "string",
        "lease_seconds": 300 (optional, default 300),
        "force_reassign": false (optional)
    }
    
    Response: ProposalFollowUpClaimV1 on success, conflict object on 409
    """
    data = request.get_json() or {}
    
    dispatch_id = data.get("dispatch_id")
    proposal_id = data.get("proposal_id")
    worker_id = data.get("worker_id")
    lease_seconds = data.get("lease_seconds", 300)
    force_reassign = data.get("force_reassign", False)
    
    if not dispatch_id or not proposal_id or not worker_id:
        return jsonify({
            "error": "dispatch_id, proposal_id, and worker_id are required",
        }), 400
    
    store = get_proposal_follow_up_claim_store()
    claim, conflict = store.claim(
        dispatch_id=dispatch_id,
        proposal_id=proposal_id,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        force_reassign=force_reassign,
    )
    
    if conflict:
        return jsonify({
            "error": "claim_conflict",
            "conflict": conflict,
        }), 409
    
    return jsonify(claim.to_dict()), 201


@proposal_claims_bp.route("/claims", methods=["GET"])
def get_claims() -> tuple[Any, int]:
    """Get aggregated claim summary.
    
    Query params:
    - since_revision: int (optional)
    - recent_limit: int (optional, default 10)
    - worker_id: string (optional)
    
    Response: ProposalFollowUpClaimSummaryV1
    """
    since_revision: int | None = None
    if request.args.get("since_revision"):
        try:
            since_revision = int(request.args.get("since_revision"))
        except (ValueError, TypeError):
            pass
    
    recent_limit = 10
    if request.args.get("recent_limit"):
        try:
            recent_limit = int(request.args.get("recent_limit"))
        except (ValueError, TypeError):
            pass
    
    worker_id = request.args.get("worker_id")
    
    store = get_proposal_follow_up_claim_store()
    summary = store.get_claim_summary(
        since_revision=since_revision,
        recent_limit=recent_limit,
        worker_id=worker_id,
    )
    
    return jsonify(summary.to_dict()), 200


@proposal_claims_bp.route("/claims/<claim_id>", methods=["GET"])
def get_claim(claim_id: str) -> tuple[Any, int]:
    """Get a single claim by ID.
    
    Response: ProposalFollowUpClaimV1
    """
    store = get_proposal_follow_up_claim_store()
    claim = store.get_claim(claim_id)
    
    if not claim:
        return jsonify({
            "error": "claim not found",
            "claim_id": claim_id,
        }), 404
    
    return jsonify(claim.to_dict()), 200


@proposal_claims_bp.route("/claims/<claim_id>/release", methods=["POST"])
def release_claim(claim_id: str) -> tuple[Any, int]:
    """Release a claim without settlement.
    
    Request body:
    {
        "worker_id": "string"
    }
    
    Response: { "released": true } or 403/404
    """
    data = request.get_json() or {}
    worker_id = data.get("worker_id")
    
    if not worker_id:
        return jsonify({
            "error": "worker_id is required",
        }), 400
    
    store = get_proposal_follow_up_claim_store()
    released = store.release_claim(claim_id, worker_id)
    
    if not released:
        return jsonify({
            "error": "release failed",
            "reason": "claim not found or wrong worker",
        }), 403
    
    return jsonify({"released": True, "claim_id": claim_id}), 200


@proposal_claims_bp.route("/claims/<claim_id>/settle", methods=["POST"])
def settle_claim(claim_id: str) -> tuple[Any, int]:
    """Settle a claim with final status.
    
    Request body:
    {
        "worker_id": "string",
        "settlement_status": "completed|abandoned|failed"
    }
    
    Response: { "settled": true } or 403/404
    """
    data = request.get_json() or {}
    worker_id = data.get("worker_id")
    settlement_status = data.get("settlement_status")
    
    if not worker_id or not settlement_status:
        return jsonify({
            "error": "worker_id and settlement_status are required",
        }), 400
    
    if settlement_status not in {"completed", "abandoned", "failed"}:
        return jsonify({
            "error": "settlement_status must be completed, abandoned, or failed",
        }), 400
    
    store = get_proposal_follow_up_claim_store()
    settled = store.settle_claim(claim_id, worker_id, settlement_status)
    
    if not settled:
        return jsonify({
            "error": "settlement failed",
            "reason": "claim not found or wrong worker",
        }), 403
    
    return jsonify({"settled": True, "claim_id": claim_id, "settlement_status": settlement_status}), 200


@proposal_claims_bp.route("/claims/worker/<worker_id>", methods=["GET"])
def get_claims_by_worker(worker_id: str) -> tuple[Any, int]:
    """Get claims for a specific worker.
    
    Query params:
    - limit: int (optional, default 50)
    
    Response: list[ProposalFollowUpClaimV1]
    """
    limit = 50
    if request.args.get("limit"):
        try:
            limit = int(request.args.get("limit"))
        except (ValueError, TypeError):
            pass
    
    store = get_proposal_follow_up_claim_store()
    claims = store.get_claims_by_worker(worker_id, limit=limit)
    
    return jsonify({
        "worker_id": worker_id,
        "claims": [c.to_dict() for c in claims],
        "count": len(claims),
    }), 200


def create_blueprint() -> Blueprint:
    """Create and return the proposal claims blueprint."""
    return proposal_claims_bp
