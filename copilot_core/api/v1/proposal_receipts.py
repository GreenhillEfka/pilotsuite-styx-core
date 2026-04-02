"""Proposal Follow-Up Receipt API for Slice 37.

Exposes worker-side delivery/queue/retry/escalation results from the same
proposal follow-up dispatch truth, enabling notification/dashboard/chat contexts
to reflect delivery outcomes without building a second history.
"""
from __future__ import annotations

from typing import Any, Optional
from flask import Blueprint, jsonify, request

from copilot_core.core.proposal_follow_up_receipt import (
    ProposalFollowUpReceipt,
    ProposalFollowUpReceiptSummary,
    get_proposal_follow_up_receipt_store,
)
from copilot_core.core.proposal_follow_up_dispatch import (
    get_proposal_follow_up_dispatch_store,
)


proposal_receipts_bp = Blueprint("proposal_receipts", __name__, url_prefix="/notifications/proposals")


@proposal_receipts_bp.route("/receipt", methods=["POST"])
def record_receipt() -> tuple[Any, int]:
    """Record a delivery receipt for a proposal follow-up dispatch.
    
    Request body:
    {
        "dispatch_id": "string",
        "proposal_id": "string",
        "delivery_status": "delivered|failed|queued|pending",
        "delivery_mode": "notification_job|reminder_queue",
        "worker_id": "string" (optional),
        "delivered_at": "ISO timestamp" (optional),
        "error": "string" (optional),
        "retry_count": 0 (optional),
        "next_retry_at": "ISO timestamp" (optional),
        "escalation_due": false (optional)
    }
    
    Response: ProposalFollowUpReceiptV1
    """
    data = request.get_json() or {}
    
    dispatch_id = data.get("dispatch_id")
    proposal_id = data.get("proposal_id")
    delivery_status = data.get("delivery_status", "unknown")
    delivery_mode = data.get("delivery_mode", "notification_job")
    worker_id = data.get("worker_id")
    delivered_at = data.get("delivered_at")
    error = data.get("error")
    retry_count = data.get("retry_count", 0)
    next_retry_at = data.get("next_retry_at")
    escalation_due = data.get("escalation_due", False)
    
    if not dispatch_id or not proposal_id:
        return jsonify({
            "error": "dispatch_id and proposal_id are required",
        }), 400
    
    store = get_proposal_follow_up_receipt_store()
    receipt = store.record_receipt(
        dispatch_id=dispatch_id,
        proposal_id=proposal_id,
        delivery_status=delivery_status,
        delivery_mode=delivery_mode,
        worker_id=worker_id,
        delivered_at=delivered_at,
        error=error,
        retry_count=retry_count,
        next_retry_at=next_retry_at,
        escalation_due=escalation_due,
    )
    
    return jsonify(receipt.to_dict()), 201


@proposal_receipts_bp.route("/receipts", methods=["GET"])
def get_receipts() -> tuple[Any, int]:
    """Get aggregated receipt summary for proposal follow-up dispatch.
    
    Query params:
    - since_revision: int (optional) - only return changes since this revision
    - recent_limit: int (optional, default 10) - number of recent receipts to include
    - worker_id: string (optional) - filter by worker
    - delivery_mode: string (optional) - filter by delivery mode
    
    Response: ProposalFollowUpReceiptSummaryV1
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
    delivery_mode = request.args.get("delivery_mode")
    
    store = get_proposal_follow_up_receipt_store()
    summary = store.get_receipt_summary(
        since_revision=since_revision,
        recent_limit=recent_limit,
        worker_id=worker_id,
        delivery_mode=delivery_mode,
    )
    
    return jsonify(summary.to_dict()), 200


@proposal_receipts_bp.route("/receipts/<receipt_id>", methods=["GET"])
def get_receipt(receipt_id: str) -> tuple[Any, int]:
    """Get a single receipt by ID.
    
    Response: ProposalFollowUpReceiptV1
    """
    store = get_proposal_follow_up_receipt_store()
    receipt = store.get_receipt(receipt_id)
    
    if not receipt:
        return jsonify({
            "error": "receipt not found",
            "receipt_id": receipt_id,
        }), 404
    
    return jsonify(receipt.to_dict()), 200


@proposal_receipts_bp.route("/receipts/proposal/<proposal_id>", methods=["GET"])
def get_receipts_by_proposal(proposal_id: str) -> tuple[Any, int]:
    """Get receipts for a specific proposal.
    
    Query params:
    - limit: int (optional, default 10) - number of receipts to return
    
    Response: list[ProposalFollowUpReceiptV1]
    """
    limit = 10
    if request.args.get("limit"):
        try:
            limit = int(request.args.get("limit"))
        except (ValueError, TypeError):
            pass
    
    store = get_proposal_follow_up_receipt_store()
    receipts = store.get_receipts_by_proposal(proposal_id, limit=limit)
    
    return jsonify({
        "proposal_id": proposal_id,
        "receipts": [r.to_dict() for r in receipts],
        "count": len(receipts),
    }), 200


@proposal_receipts_bp.route("/receipts/worker/<worker_id>", methods=["GET"])
def get_receipts_by_worker(worker_id: str) -> tuple[Any, int]:
    """Get receipts for a specific worker.
    
    Query params:
    - limit: int (optional, default 50) - number of receipts to return
    
    Response: list[ProposalFollowUpReceiptV1]
    """
    limit = 50
    if request.args.get("limit"):
        try:
            limit = int(request.args.get("limit"))
        except (ValueError, TypeError):
            pass
    
    store = get_proposal_follow_up_receipt_store()
    receipts = store.get_receipts_by_worker(worker_id, limit=limit)
    
    return jsonify({
        "worker_id": worker_id,
        "receipts": [r.to_dict() for r in receipts],
        "count": len(receipts),
    }), 200


def create_blueprint() -> Blueprint:
    """Create and return the proposal receipts blueprint."""
    return proposal_receipts_bp
