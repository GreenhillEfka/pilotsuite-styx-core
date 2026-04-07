"""Proposal Lifecycle Dispatch Worker Surfaces for Slice 35.

Materializes notification dispatch candidates from the canonical proposal lifecycle truth,
enabling notification workers to dispatch open/suggested proposals with delta cursor
and delivery mode support.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional
import hashlib
import uuid

from copilot_core.core.proposal_lifecycle_read_model import (
    ProposalLifecycleStatus,
    build_proposal_lifecycle_status_summary,
    get_action_closure_store,
)
from copilot_core.action_closure import ActionClosureStore


@dataclass
class ProposalLifecycleDispatchCandidate:
    """Single proposal dispatch candidate for notification workers."""
    proposal_id: str
    lifecycle_status: str
    zone_id: str | None = None
    module_id: str | None = None
    action_id: str | None = None
    closure_id: str | None = None
    source: str | None = None
    title: str | None = None
    summary: str | None = None
    confidence: float | None = None
    accepted_at: str | None = None
    latest_change_at: str | None = None
    revision: int = 0
    priority: str = "normal"
    delivery_mode: str = "notification_job"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalLifecycleDispatchCandidateV1",
            "proposal_id": self.proposal_id,
            "lifecycle_status": self.lifecycle_status,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "action_id": self.action_id,
            "closure_id": self.closure_id,
            "source": self.source,
            "title": self.title,
            "summary": self.summary,
            "confidence": self.confidence,
            "accepted_at": self.accepted_at,
            "latest_change_at": self.latest_change_at,
            "revision": self.revision,
            "priority": self.priority,
            "delivery_mode": self.delivery_mode,
        }


@dataclass
class ProposalLifecycleDispatchCursor:
    """Cursor for incremental polling of proposal dispatch candidates."""
    since_revision: int | None = None
    current_revision: int = 0
    has_changes: bool = False
    latest_change_at: str | None = None
    candidate_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalLifecycleDispatchCursorV1",
            "since_revision": self.since_revision,
            "current_revision": self.current_revision,
            "has_changes": self.has_changes,
            "latest_change_at": self.latest_change_at,
            "candidate_count": self.candidate_count,
        }


@dataclass
class ProposalLifecycleDispatchBundle:
    """Complete dispatch bundle for notification workers."""
    candidates: list[ProposalLifecycleDispatchCandidate] = field(default_factory=list)
    cursor: ProposalLifecycleDispatchCursor = field(default_factory=ProposalLifecycleDispatchCursor)
    delivery_mode: str = "notification_job"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalLifecycleDispatchV1",
            "candidates": [c.to_dict() for c in self.candidates],
            "cursor": self.cursor.to_dict(),
            "delivery_mode": self.delivery_mode,
            "counts": {
                "dispatchable": len(self.candidates),
                "by_status": _count_by_status(self.candidates),
                "by_source": _count_by_source(self.candidates),
            },
        }


def _count_by_status(candidates: list[ProposalLifecycleDispatchCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.lifecycle_status] = counts.get(c.lifecycle_status, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def _count_by_source(candidates: list[ProposalLifecycleDispatchCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in candidates:
        source = c.source or "unknown"
        counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def _compute_candidate_id(proposal_id: str, delivery_mode: str) -> str:
    """Compute stable dispatch candidate ID."""
    raw = f"{proposal_id}:{delivery_mode}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _determine_priority(lifecycle_status: str, source: str | None = None) -> str:
    """Determine dispatch priority based on lifecycle status and source."""
    high_priority_states = {"failed", "rejected", "cancelled", "error"}
    if lifecycle_status in high_priority_states:
        return "high"
    if lifecycle_status in {"accepted", "pending", "queued"}:
        return "normal"
    if lifecycle_status in {"proposed", "suggested"}:
        return "low"
    return "normal"


class ProposalLifecycleDispatchStore:
    """In-memory store for proposal lifecycle dispatch tracking."""
    
    def __init__(self) -> None:
        self._candidates: dict[str, dict[str, Any]] = {}
        self._claims: dict[str, dict[str, Any]] = {}
        self._acknowledgements: dict[str, dict[str, Any]] = {}
        self._receipts: dict[str, dict[str, Any]] = {}
        self._settlements: dict[str, dict[str, Any]] = {}
        self._revision = 0
    
    def clear(self) -> None:
        """Clear all store data."""
        self._candidates.clear()
        self._claims.clear()
        self._acknowledgements.clear()
        self._receipts.clear()
        self._settlements.clear()
        self._revision = 0
    
    def materialize_candidates(
        self,
        lifecycle_summary: dict[str, Any] | object,
        delivery_mode: str = "notification_job",
        recent_limit: int = 10,
    ) -> ProposalLifecycleDispatchBundle:
        """Materialize dispatch candidates from lifecycle summary."""
        candidates: list[ProposalLifecycleDispatchCandidate] = []
        
        # Handle both dict and ReadModel objects
        if hasattr(lifecycle_summary, "to_dict"):
            summary_dict = lifecycle_summary.to_dict()
        else:
            summary_dict = lifecycle_summary
        
        recent_statuses = summary_dict.get("recent_statuses", [])
        for item in recent_statuses[:recent_limit]:
            lifecycle_status = item.get("lifecycle_status", "unknown")
            if lifecycle_status not in {"proposed", "suggested", "accepted", "pending", "failed", "rejected"}:
                continue
            
            proposal_id = item.get("proposal_id", "")
            candidate_id = _compute_candidate_id(proposal_id, delivery_mode)
            
            candidate = ProposalLifecycleDispatchCandidate(
                proposal_id=proposal_id,
                lifecycle_status=lifecycle_status,
                zone_id=item.get("zone_id"),
                module_id=item.get("module_id"),
                action_id=item.get("action_id"),
                closure_id=item.get("closure_id"),
                source=item.get("source"),
                title=item.get("title"),
                summary=item.get("summary"),
                confidence=item.get("confidence"),
                accepted_at=item.get("accepted_at"),
                latest_change_at=item.get("latest_change_at"),
                revision=item.get("revision", 0),
                priority=_determine_priority(lifecycle_status, item.get("source")),
                delivery_mode=delivery_mode,
            )
            candidates.append(candidate)
            
            if candidate_id not in self._candidates:
                self._candidates[candidate_id] = {
                    "candidate_id": candidate_id,
                    "proposal_id": proposal_id,
                    "delivery_mode": delivery_mode,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "acknowledged": False,
                    "claimed": False,
                    "settled": False,
                }
        
        current_revision = summary_dict.get("revision", 0)
        since_revision = summary_dict.get("since_revision")
        
        cursor = ProposalLifecycleDispatchCursor(
            since_revision=since_revision,
            current_revision=current_revision,
            has_changes=len(candidates) > 0,
            latest_change_at=summary_dict.get("latest_change_at"),
            candidate_count=len(candidates),
        )
        
        return ProposalLifecycleDispatchBundle(
            candidates=candidates,
            cursor=cursor,
            delivery_mode=delivery_mode,
        )
    
    def claim(
        self,
        candidate_ids: list[str],
        worker_id: str,
        lease_seconds: int = 300,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Claim dispatch candidates for a worker."""
        claims = []
        conflicts = []
        
        now = datetime.now(timezone.utc).isoformat()
        for candidate_id in candidate_ids:
            if candidate_id not in self._candidates:
                conflicts.append({
                    "candidate_id": candidate_id,
                    "reason": "not_found",
                    "message": "Candidate does not exist",
                })
                continue
            
            candidate = self._candidates[candidate_id]
            if candidate.get("claimed") and candidate.get("claim_worker_id") != worker_id:
                conflicts.append({
                    "candidate_id": candidate_id,
                    "reason": "already_claimed",
                    "claimed_by": candidate.get("claim_worker_id"),
                })
                continue
            
            claim = {
                "claim_id": str(uuid.uuid4()),
                "candidate_id": candidate_id,
                "worker_id": worker_id,
                "lease_seconds": lease_seconds,
                "claimed_at": now,
                "expires_at": now,
            }
            self._claims[candidate_id] = claim
            candidate["claimed"] = True
            candidate["claim_worker_id"] = worker_id
            self._revision += 1
            claims.append(claim)
        
        return claims, conflicts
    
    def acknowledge(
        self,
        candidate_ids: list[str],
        worker_id: str,
    ) -> list[dict[str, Any]]:
        """Acknowledge dispatch candidates."""
        acknowledgements = []
        now = datetime.now(timezone.utc).isoformat()
        
        for candidate_id in candidate_ids:
            if candidate_id not in self._candidates:
                continue
            
            ack = {
                "ack_id": str(uuid.uuid4()),
                "candidate_id": candidate_id,
                "worker_id": worker_id,
                "acknowledged_at": now,
            }
            self._acknowledgements[candidate_id] = ack
            self._candidates[candidate_id]["acknowledged"] = True
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
            candidate_id = receipt.get("candidate_id")
            if not candidate_id or candidate_id not in self._candidates:
                continue
            
            receipt_record = {
                "receipt_id": str(uuid.uuid4()),
                "candidate_id": candidate_id,
                "delivery_status": receipt.get("delivery_status", "unknown"),
                "delivered_at": receipt.get("delivered_at", now),
                "error": receipt.get("error"),
                "retry_count": receipt.get("retry_count", 0),
                "recorded_at": now,
            }
            self._receipts[candidate_id] = receipt_record
            self._revision += 1
            recorded.append(receipt_record)
        
        return recorded
    
    def settle_claims(
        self,
        settlements: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Settle claims for dispatch candidates."""
        settled = []
        conflicts = []
        now = datetime.now(timezone.utc).isoformat()
        
        for settlement in settlements:
            candidate_id = settlement.get("candidate_id")
            if not candidate_id or candidate_id not in self._candidates:
                conflicts.append({
                    "candidate_id": candidate_id,
                    "reason": "not_found",
                })
                continue
            
            candidate = self._candidates[candidate_id]
            if not candidate.get("claimed"):
                conflicts.append({
                    "candidate_id": candidate_id,
                    "reason": "not_claimed",
                })
                continue
            
            settlement_record = {
                "settlement_id": str(uuid.uuid4()),
                "candidate_id": candidate_id,
                "settlement_status": settlement.get("settlement_status", "completed"),
                "settled_at": now,
                "outcome": settlement.get("outcome"),
            }
            self._settlements[candidate_id] = settlement_record
            candidate["settled"] = True
            self._revision += 1
            settled.append(settlement_record)
        
        return settled, conflicts
    
    def get_revision(self) -> int:
        """Get current revision."""
        return self._revision


_proposal_lifecycle_dispatch_store: Optional[ProposalLifecycleDispatchStore] = None


def get_proposal_lifecycle_dispatch_store() -> ProposalLifecycleDispatchStore:
    """Get or create the proposal lifecycle dispatch store."""
    global _proposal_lifecycle_dispatch_store
    if _proposal_lifecycle_dispatch_store is None:
        _proposal_lifecycle_dispatch_store = ProposalLifecycleDispatchStore()
    return _proposal_lifecycle_dispatch_store
