"""Proposal Follow-Up Receipt Surface for Slice 37.

Materializes worker-side delivery/queue/retry/escalation results from the same
proposal follow-up dispatch truth, enabling notification/dashboard/chat contexts
to reflect delivery outcomes without building a second history.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class ProposalFollowUpReceipt:
    """Single delivery receipt for a proposal follow-up dispatch."""
    receipt_id: str
    dispatch_id: str
    proposal_id: str
    delivery_status: str  # delivered, failed, queued, pending
    delivery_mode: str  # notification_job, reminder_queue
    worker_id: str | None = None
    delivered_at: str | None = None
    error: str | None = None
    retry_count: int = 0
    next_retry_at: str | None = None
    escalation_due: bool = False
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalFollowUpReceiptV1",
            "receipt_id": self.receipt_id,
            "dispatch_id": self.dispatch_id,
            "proposal_id": self.proposal_id,
            "delivery_status": self.delivery_status,
            "delivery_mode": self.delivery_mode,
            "worker_id": self.worker_id,
            "delivered_at": self.delivered_at,
            "error": self.error,
            "retry_count": self.retry_count,
            "next_retry_at": self.next_retry_at,
            "escalation_due": self.escalation_due,
            "recorded_at": self.recorded_at,
        }


@dataclass
class ProposalFollowUpReceiptSummary:
    """Aggregated receipt summary for proposal follow-up dispatch."""
    receipt_revision: int = 0
    latest_change_at: str | None = None
    total_receipts: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_delivery_mode: dict[str, int] = field(default_factory=dict)
    by_worker: dict[str, int] = field(default_factory=dict)
    recent_receipts: list[ProposalFollowUpReceipt] = field(default_factory=list)
    has_changes: bool = False
    since_revision: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalFollowUpReceiptSummaryV1",
            "receipt_revision": self.receipt_revision,
            "latest_change_at": self.latest_change_at,
            "total_receipts": self.total_receipts,
            "by_status": self.by_status,
            "by_delivery_mode": self.by_delivery_mode,
            "by_worker": self.by_worker,
            "recent_receipts": [r.to_dict() for r in self.recent_receipts],
            "has_changes": self.has_changes,
            "since_revision": self.since_revision,
        }


class ProposalFollowUpReceiptStore:
    """In-memory store for proposal follow-up receipt tracking."""
    
    def __init__(self) -> None:
        self._receipts: dict[str, dict[str, Any]] = {}
        self._by_proposal: dict[str, list[str]] = {}
        self._by_worker: dict[str, list[str]] = {}
        self._revision = 0
        self._latest_change_at: str | None = None
    
    def clear(self) -> None:
        """Clear all store data."""
        self._receipts.clear()
        self._by_proposal.clear()
        self._by_worker.clear()
        self._revision = 0
        self._latest_change_at = None
    
    def record_receipt(
        self,
        dispatch_id: str,
        proposal_id: str,
        delivery_status: str,
        delivery_mode: str = "notification_job",
        worker_id: str | None = None,
        delivered_at: str | None = None,
        error: str | None = None,
        retry_count: int = 0,
        next_retry_at: str | None = None,
        escalation_due: bool = False,
    ) -> ProposalFollowUpReceipt:
        """Record a delivery receipt for a proposal follow-up dispatch."""
        now = datetime.now(timezone.utc)
        receipt_id = f"receipt_{dispatch_id}_{self._revision}"
        
        receipt = ProposalFollowUpReceipt(
            receipt_id=receipt_id,
            dispatch_id=dispatch_id,
            proposal_id=proposal_id,
            delivery_status=delivery_status,
            delivery_mode=delivery_mode,
            worker_id=worker_id,
            delivered_at=delivered_at or now.isoformat(),
            error=error,
            retry_count=retry_count,
            next_retry_at=next_retry_at,
            escalation_due=escalation_due,
            recorded_at=now.isoformat(),
        )
        
        self._receipts[receipt_id] = {
            "receipt_id": receipt_id,
            "dispatch_id": dispatch_id,
            "proposal_id": proposal_id,
            "delivery_status": delivery_status,
            "delivery_mode": delivery_mode,
            "worker_id": worker_id,
            "delivered_at": delivered_at or now.isoformat(),
            "error": error,
            "retry_count": retry_count,
            "next_retry_at": next_retry_at,
            "escalation_due": escalation_due,
            "recorded_at": now.isoformat(),
        }
        
        # Index by proposal_id
        if proposal_id not in self._by_proposal:
            self._by_proposal[proposal_id] = []
        self._by_proposal[proposal_id].append(receipt_id)
        
        # Index by worker_id
        if worker_id:
            if worker_id not in self._by_worker:
                self._by_worker[worker_id] = []
            self._by_worker[worker_id].append(receipt_id)
        
        self._revision += 1
        self._latest_change_at = now.isoformat()
        
        return receipt
    
    def get_receipt(self, receipt_id: str) -> ProposalFollowUpReceipt | None:
        """Get a single receipt by ID."""
        data = self._receipts.get(receipt_id)
        if not data:
            return None
        return ProposalFollowUpReceipt(
            receipt_id=data["receipt_id"],
            dispatch_id=data["dispatch_id"],
            proposal_id=data["proposal_id"],
            delivery_status=data["delivery_status"],
            delivery_mode=data["delivery_mode"],
            worker_id=data.get("worker_id"),
            delivered_at=data.get("delivered_at"),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            next_retry_at=data.get("next_retry_at"),
            escalation_due=data.get("escalation_due", False),
            recorded_at=data.get("recorded_at"),
        )
    
    def get_receipts_by_proposal(
        self,
        proposal_id: str,
        limit: int = 10,
    ) -> list[ProposalFollowUpReceipt]:
        """Get receipts for a specific proposal."""
        receipt_ids = self._by_proposal.get(proposal_id, [])
        receipts = []
        for rid in receipt_ids[-limit:]:
            receipt = self.get_receipt(rid)
            if receipt:
                receipts.append(receipt)
        return receipts
    
    def get_receipts_by_worker(
        self,
        worker_id: str,
        limit: int = 50,
    ) -> list[ProposalFollowUpReceipt]:
        """Get receipts for a specific worker."""
        receipt_ids = self._by_worker.get(worker_id, [])
        receipts = []
        for rid in receipt_ids[-limit:]:
            receipt = self.get_receipt(rid)
            if receipt:
                receipts.append(receipt)
        return receipts
    
    def get_receipt_summary(
        self,
        since_revision: int | None = None,
        recent_limit: int = 10,
        worker_id: str | None = None,
        delivery_mode: str | None = None,
    ) -> ProposalFollowUpReceiptSummary:
        """Get aggregated receipt summary."""
        # Filter receipts
        filtered_receipts = list(self._receipts.values())
        
        if worker_id:
            filtered_receipts = [r for r in filtered_receipts if r.get("worker_id") == worker_id]
        
        if delivery_mode:
            filtered_receipts = [r for r in filtered_receipts if r.get("delivery_mode") == delivery_mode]
        
        if since_revision is not None:
            # Filter by revision (simplified: use recorded_at ordering)
            filtered_receipts = [r for r in filtered_receipts if r.get("_revision", 0) > since_revision]
        
        # Count by status
        by_status: dict[str, int] = {}
        by_delivery_mode: dict[str, int] = {}
        by_worker: dict[str, int] = {}
        
        for r in filtered_receipts:
            status = r.get("delivery_status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1
            
            mode = r.get("delivery_mode", "unknown")
            by_delivery_mode[mode] = by_delivery_mode.get(mode, 0) + 1
            
            worker = r.get("worker_id", "unknown")
            by_worker[worker] = by_worker.get(worker, 0) + 1
        
        # Get recent receipts
        recent_receipts = []
        sorted_receipts = sorted(
            filtered_receipts,
            key=lambda r: r.get("recorded_at", ""),
            reverse=True,
        )[:recent_limit]
        
        for r in sorted_receipts:
            receipt = ProposalFollowUpReceipt(
                receipt_id=r["receipt_id"],
                dispatch_id=r["dispatch_id"],
                proposal_id=r["proposal_id"],
                delivery_status=r["delivery_status"],
                delivery_mode=r["delivery_mode"],
                worker_id=r.get("worker_id"),
                delivered_at=r.get("delivered_at"),
                error=r.get("error"),
                retry_count=r.get("retry_count", 0),
                next_retry_at=r.get("next_retry_at"),
                escalation_due=r.get("escalation_due", False),
                recorded_at=r.get("recorded_at"),
            )
            recent_receipts.append(receipt)
        
        has_changes = since_revision is None or self._revision > since_revision
        
        return ProposalFollowUpReceiptSummary(
            receipt_revision=self._revision,
            latest_change_at=self._latest_change_at,
            total_receipts=len(filtered_receipts),
            by_status=dict(sorted(by_status.items(), key=lambda x: (-x[1], x[0]))),
            by_delivery_mode=dict(sorted(by_delivery_mode.items(), key=lambda x: (-x[1], x[0]))),
            by_worker=dict(sorted(by_worker.items(), key=lambda x: (-x[1], x[0]))),
            recent_receipts=recent_receipts,
            has_changes=has_changes,
            since_revision=since_revision,
        )
    
    def get_revision(self) -> int:
        """Get current revision."""
        return self._revision


_proposal_follow_up_receipt_store: Optional[ProposalFollowUpReceiptStore] = None


def get_proposal_follow_up_receipt_store() -> ProposalFollowUpReceiptStore:
    """Get or create the proposal follow-up receipt store."""
    global _proposal_follow_up_receipt_store
    if _proposal_follow_up_receipt_store is None:
        _proposal_follow_up_receipt_store = ProposalFollowUpReceiptStore()
    return _proposal_follow_up_receipt_store
