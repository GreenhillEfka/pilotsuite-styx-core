"""Proposal Follow-Up Dispatch Worker for Slice 36.

Materializes notification jobs and reminder queues from the canonical proposal lifecycle
dispatch truth, enabling workers to dispatch open/suggested proposals with delta cursor,
acknowledgement mechanics, and delivery status tracking.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import hashlib
import uuid


@dataclass
class ProposalFollowUpDispatchCandidate:
    """Single proposal follow-up dispatch candidate for notification workers."""
    proposal_id: str
    lifecycle_status: str
    zone_id: str | None = None
    module_id: str | None = None
    source: str | None = None
    title: str | None = None
    summary: str | None = None
    priority: str = "normal"
    delivery_mode: str = "notification_job"
    dispatch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalFollowUpDispatchCandidateV1",
            "proposal_id": self.proposal_id,
            "lifecycle_status": self.lifecycle_status,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "source": self.source,
            "title": self.title,
            "summary": self.summary,
            "priority": self.priority,
            "delivery_mode": self.delivery_mode,
            "dispatch_id": self.dispatch_id,
            "created_at": self.created_at,
        }


@dataclass
class ProposalFollowUpDispatchCursor:
    """Cursor for incremental polling of proposal follow-up dispatch candidates."""
    since_revision: int | None = None
    current_revision: int = 0
    has_changes: bool = False
    latest_change_at: str | None = None
    candidate_count: int = 0
    pending_ack_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalFollowUpDispatchCursorV1",
            "since_revision": self.since_revision,
            "current_revision": self.current_revision,
            "has_changes": self.has_changes,
            "latest_change_at": self.latest_change_at,
            "candidate_count": self.candidate_count,
            "pending_ack_count": self.pending_ack_count,
        }


@dataclass
class ProposalFollowUpDispatchBundle:
    """Complete dispatch bundle for notification workers."""
    candidates: list[ProposalFollowUpDispatchCandidate] = field(default_factory=list)
    cursor: ProposalFollowUpDispatchCursor = field(default_factory=ProposalFollowUpDispatchCursor)
    delivery_mode: str = "notification_job"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalFollowUpDispatchV1",
            "candidates": [c.to_dict() for c in self.candidates],
            "cursor": self.cursor.to_dict(),
            "delivery_mode": self.delivery_mode,
            "counts": {
                "dispatchable": len(self.candidates),
                "by_status": _count_by_status(self.candidates),
                "by_source": _count_by_source(self.candidates),
                "by_priority": _count_by_priority(self.candidates),
            },
        }


def _count_by_status(candidates: list[ProposalFollowUpDispatchCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.lifecycle_status] = counts.get(c.lifecycle_status, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def _count_by_source(candidates: list[ProposalFollowUpDispatchCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in candidates:
        source = c.source or "unknown"
        counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def _count_by_priority(candidates: list[ProposalFollowUpDispatchCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.priority] = counts.get(c.priority, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def _compute_dispatch_id(proposal_id: str, delivery_mode: str) -> str:
    """Compute stable dispatch ID."""
    raw = f"{proposal_id}:{delivery_mode}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ProposalFollowUpDispatchStore:
    """In-memory store for proposal follow-up dispatch tracking."""
    
    def __init__(self) -> None:
        self._candidates: dict[str, dict[str, Any]] = {}
        self._acks: dict[str, dict[str, Any]] = {}
        self._receipts: dict[str, dict[str, Any]] = {}
        self._revision = 0
    
    def clear(self) -> None:
        """Clear all store data."""
        self._candidates.clear()
        self._acks.clear()
        self._receipts.clear()
        self._revision = 0
    
    def materialize_from_dispatch_bundle(
        self,
        dispatch_bundle: dict[str, Any],
    ) -> ProposalFollowUpDispatchBundle:
        """Materialize follow-up candidates from dispatch bundle."""
        candidates: list[ProposalFollowUpDispatchCandidate] = []
        
        dispatch_candidates = dispatch_bundle.get("candidates", [])
        delivery_mode = dispatch_bundle.get("delivery_mode", "notification_job")
        
        for item in dispatch_candidates:
            proposal_id = item.get("proposal_id", "")
            dispatch_id = _compute_dispatch_id(proposal_id, delivery_mode)
            
            candidate = ProposalFollowUpDispatchCandidate(
                proposal_id=proposal_id,
                lifecycle_status=item.get("lifecycle_status", "unknown"),
                zone_id=item.get("zone_id"),
                module_id=item.get("module_id"),
                source=item.get("source"),
                title=item.get("title"),
                summary=item.get("summary"),
                priority=item.get("priority", "normal"),
                delivery_mode=delivery_mode,
                dispatch_id=dispatch_id,
            )
            candidates.append(candidate)
            
            if dispatch_id not in self._candidates:
                self._candidates[dispatch_id] = {
                    "dispatch_id": dispatch_id,
                    "proposal_id": proposal_id,
                    "delivery_mode": delivery_mode,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "acknowledged": False,
                    "delivered": False,
                }
        
        cursor_dict = dispatch_bundle.get("cursor", {})
        cursor = ProposalFollowUpDispatchCursor(
            since_revision=cursor_dict.get("since_revision"),
            current_revision=cursor_dict.get("current_revision", 0),
            has_changes=cursor_dict.get("has_changes", False),
            latest_change_at=cursor_dict.get("latest_change_at"),
            candidate_count=len(candidates),
            pending_ack_count=sum(1 for c in self._candidates.values() if not c.get("acknowledged")),
        )
        
        return ProposalFollowUpDispatchBundle(
            candidates=candidates,
            cursor=cursor,
            delivery_mode=delivery_mode,
        )
    
    def acknowledge(
        self,
        dispatch_ids: list[str],
        worker_id: str,
    ) -> list[dict[str, Any]]:
        """Acknowledge dispatch candidates."""
        acknowledgements = []
        now = datetime.now(timezone.utc).isoformat()
        
        for dispatch_id in dispatch_ids:
            if dispatch_id not in self._candidates:
                continue
            
            ack = {
                "ack_id": str(uuid.uuid4()),
                "dispatch_id": dispatch_id,
                "worker_id": worker_id,
                "acknowledged_at": now,
            }
            self._acks[dispatch_id] = ack
            self._candidates[dispatch_id]["acknowledged"] = True
            self._candidates[dispatch_id]["ack_worker_id"] = worker_id
            self._revision += 1
            acknowledgements.append(ack)
        
        return acknowledgements
    
    def record_receipts(
        self,
        receipts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Record delivery receipts for dispatch candidates."""
        recorded = []
        now = datetime.now(timezone.utc).isoformat()
        
        for receipt in receipts:
            dispatch_id = receipt.get("dispatch_id")
            if not dispatch_id or dispatch_id not in self._candidates:
                continue
            
            receipt_record = {
                "receipt_id": str(uuid.uuid4()),
                "dispatch_id": dispatch_id,
                "delivery_status": receipt.get("delivery_status", "unknown"),
                "delivered_at": receipt.get("delivered_at", now),
                "error": receipt.get("error"),
                "retry_count": receipt.get("retry_count", 0),
                "recorded_at": now,
            }
            self._receipts[dispatch_id] = receipt_record
            self._candidates[dispatch_id]["delivered"] = receipt.get("delivery_status") == "delivered"
            self._revision += 1
            recorded.append(receipt_record)
        
        return recorded
    
    def get_revision(self) -> int:
        """Get current revision."""
        return self._revision
    
    def get_pending_ack_count(self) -> int:
        """Get count of candidates pending acknowledgement."""
        return sum(1 for c in self._candidates.values() if not c.get("acknowledged"))


_proposal_follow_up_dispatch_store: Optional[ProposalFollowUpDispatchStore] = None


def get_proposal_follow_up_dispatch_store() -> ProposalFollowUpDispatchStore:
    """Get or create the proposal follow-up dispatch store."""
    global _proposal_follow_up_dispatch_store
    if _proposal_follow_up_dispatch_store is None:
        _proposal_follow_up_dispatch_store = ProposalFollowUpDispatchStore()
    return _proposal_follow_up_dispatch_store
