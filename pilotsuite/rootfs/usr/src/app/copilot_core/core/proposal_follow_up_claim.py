"""Proposal Follow-Up Claim / Lease Surface for Slice 38.

Enables workers to claim proposal follow-ups from the same dispatch/receipt truth
with lease expiry, reassign visibility, and escalation relevance without building
a second worker lock logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional


@dataclass
class ProposalFollowUpClaim:
    """Single claim for a proposal follow-up dispatch candidate."""
    claim_id: str
    dispatch_id: str
    proposal_id: str
    worker_id: str
    lease_seconds: int = 300
    claimed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    released: bool = False
    released_at: str | None = None
    settlement_status: str | None = None  # completed, abandoned, failed
    settled_at: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalFollowUpClaimV1",
            "claim_id": self.claim_id,
            "dispatch_id": self.dispatch_id,
            "proposal_id": self.proposal_id,
            "worker_id": self.worker_id,
            "lease_seconds": self.lease_seconds,
            "claimed_at": self.claimed_at,
            "expires_at": self.expires_at,
            "released": self.released,
            "released_at": self.released_at,
            "settlement_status": self.settlement_status,
            "settled_at": self.settled_at,
        }
    
    def is_expired(self) -> bool:
        """Check if claim lease has expired."""
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return now > expires
    
    def is_active(self) -> bool:
        """Check if claim is still active (not expired, not released, not settled)."""
        return not self.released and self.settlement_status is None and not self.is_expired()
    
    def is_reassignable(self) -> bool:
        """Check if claim can be reassigned (expired or abandoned)."""
        return self.is_expired() or (self.released and not self.settlement_status)


@dataclass
class ProposalFollowUpClaimSummary:
    """Aggregated claim summary for proposal follow-up dispatch."""
    claim_revision: int = 0
    latest_change_at: str | None = None
    total_claims: int = 0
    active_claims: int = 0
    expired_claims: int = 0
    released_claims: int = 0
    settled_claims: int = 0
    reassignable_claims: int = 0
    by_worker: dict[str, int] = field(default_factory=dict)
    by_delivery_mode: dict[str, int] = field(default_factory=dict)
    recent_claims: list[ProposalFollowUpClaim] = field(default_factory=list)
    has_changes: bool = False
    since_revision: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalFollowUpClaimSummaryV1",
            "claim_revision": self.claim_revision,
            "latest_change_at": self.latest_change_at,
            "total_claims": self.total_claims,
            "active_claims": self.active_claims,
            "expired_claims": self.expired_claims,
            "released_claims": self.released_claims,
            "settled_claims": self.settled_claims,
            "reassignable_claims": self.reassignable_claims,
            "by_worker": self.by_worker,
            "by_delivery_mode": self.by_delivery_mode,
            "recent_claims": [c.to_dict() for c in self.recent_claims],
            "has_changes": self.has_changes,
            "since_revision": self.since_revision,
        }


class ProposalFollowUpClaimStore:
    """In-memory store for proposal follow-up claim tracking."""
    
    def __init__(self) -> None:
        self._claims: dict[str, dict[str, Any]] = {}
        self._by_dispatch: dict[str, str] = {}  # dispatch_id -> claim_id
        self._by_worker: dict[str, list[str]] = {}
        self._revision = 0
        self._latest_change_at: str | None = None
    
    def clear(self) -> None:
        """Clear all store data."""
        self._claims.clear()
        self._by_dispatch.clear()
        self._by_worker.clear()
        self._revision = 0
        self._latest_change_at = None
    
    def claim(
        self,
        dispatch_id: str,
        proposal_id: str,
        worker_id: str,
        lease_seconds: int = 300,
        force_reassign: bool = False,
    ) -> tuple[ProposalFollowUpClaim | None, Optional[dict[str, Any]]]:
        """Claim a proposal follow-up dispatch candidate.
        
        Returns:
            Tuple of (claim, conflict) where conflict is None on success.
        """
        now = datetime.now(timezone.utc)
        
        # Check if already claimed
        existing_claim_id = self._by_dispatch.get(dispatch_id)
        if existing_claim_id:
            existing = self._claims.get(existing_claim_id)
            if existing:
                # Check if existing claim is still active
                is_expired = datetime.fromisoformat(existing["expires_at"].replace("Z", "+00:00")) < now
                is_released = existing.get("released", False)
                is_settled = existing.get("settlement_status") is not None
                
                if not is_expired and not is_released and not is_settled:
                    # Still active - check if same worker
                    if existing["worker_id"] != worker_id:
                        return None, {
                            "reason": "already_claimed",
                            "claimed_by": existing["worker_id"],
                            "expires_at": existing["expires_at"],
                        }
                    else:
                        # Same worker re-claiming - extend lease
                        existing_claim = self.get_claim(existing_claim_id)
                        if existing_claim:
                            return existing_claim, None
                
                # Expired or released - allow reassign
                if not force_reassign and not is_expired:
                    # Released but not expired - still allow
                    pass
        
        # Create new claim
        claim_id = f"claim_{dispatch_id}_{self._revision}"
        expires_at = now + timedelta(seconds=lease_seconds)
        
        claim = ProposalFollowUpClaim(
            claim_id=claim_id,
            dispatch_id=dispatch_id,
            proposal_id=proposal_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            claimed_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
        )
        
        self._claims[claim_id] = {
            "claim_id": claim_id,
            "dispatch_id": dispatch_id,
            "proposal_id": proposal_id,
            "worker_id": worker_id,
            "lease_seconds": lease_seconds,
            "claimed_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "released": False,
            "settlement_status": None,
        }
        
        self._by_dispatch[dispatch_id] = claim_id
        
        if worker_id not in self._by_worker:
            self._by_worker[worker_id] = []
        self._by_worker[worker_id].append(claim_id)
        
        self._revision += 1
        self._latest_change_at = now.isoformat()
        
        return claim, None
    
    def release_claim(
        self,
        claim_id: str,
        worker_id: str,
    ) -> bool:
        """Release a claim without settlement."""
        if claim_id not in self._claims:
            return False
        
        claim = self._claims[claim_id]
        if claim["worker_id"] != worker_id:
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        claim["released"] = True
        claim["released_at"] = now
        
        self._revision += 1
        self._latest_change_at = now
        
        return True
    
    def settle_claim(
        self,
        claim_id: str,
        worker_id: str,
        settlement_status: str,  # completed, abandoned, failed
    ) -> bool:
        """Settle a claim with final status."""
        if claim_id not in self._claims:
            return False
        
        claim = self._claims[claim_id]
        if claim["worker_id"] != worker_id:
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        claim["settlement_status"] = settlement_status
        claim["settled_at"] = now
        
        self._revision += 1
        self._latest_change_at = now
        
        return True
    
    def get_claim(self, claim_id: str) -> ProposalFollowUpClaim | None:
        """Get a single claim by ID."""
        data = self._claims.get(claim_id)
        if not data:
            return None
        
        return ProposalFollowUpClaim(
            claim_id=data["claim_id"],
            dispatch_id=data["dispatch_id"],
            proposal_id=data["proposal_id"],
            worker_id=data["worker_id"],
            lease_seconds=data["lease_seconds"],
            claimed_at=data["claimed_at"],
            expires_at=data["expires_at"],
            released=data.get("released", False),
            released_at=data.get("released_at"),
            settlement_status=data.get("settlement_status"),
            settled_at=data.get("settled_at"),
        )
    
    def get_claims_by_worker(
        self,
        worker_id: str,
        limit: int = 50,
    ) -> list[ProposalFollowUpClaim]:
        """Get claims for a specific worker."""
        claim_ids = self._by_worker.get(worker_id, [])
        claims = []
        for cid in claim_ids[-limit:]:
            claim = self.get_claim(cid)
            if claim:
                claims.append(claim)
        return claims
    
    def get_claim_summary(
        self,
        since_revision: int | None = None,
        recent_limit: int = 10,
        worker_id: str | None = None,
        delivery_mode: str | None = None,
    ) -> ProposalFollowUpClaimSummary:
        """Get aggregated claim summary."""
        now = datetime.now(timezone.utc)
        
        # Filter claims
        filtered_claims = list(self._claims.values())
        
        if worker_id:
            filtered_claims = [c for c in filtered_claims if c.get("worker_id") == worker_id]
        
        # Count states
        active_count = 0
        expired_count = 0
        released_count = 0
        settled_count = 0
        reassignable_count = 0
        
        by_worker: dict[str, int] = {}
        by_delivery_mode: dict[str, int] = {}
        
        recent_claims = []
        
        for c in filtered_claims:
            expires_at = datetime.fromisoformat(c["expires_at"].replace("Z", "+00:00"))
            is_expired = now > expires_at
            is_released = c.get("released", False)
            is_settled = c.get("settlement_status") is not None
            
            worker = c.get("worker_id", "unknown")
            by_worker[worker] = by_worker.get(worker, 0) + 1
            
            # Delivery mode from dispatch_id pattern (simplified)
            mode = "notification_job" if "notif" in c["dispatch_id"] else "reminder_queue"
            by_delivery_mode[mode] = by_delivery_mode.get(mode, 0) + 1
            
            if is_settled:
                settled_count += 1
            elif is_released:
                released_count += 1
                if is_expired:
                    reassignable_count += 1
            elif is_expired:
                expired_count += 1
                reassignable_count += 1
            else:
                active_count += 1
            
            # Build claim object for recent list
            claim = ProposalFollowUpClaim(
                claim_id=c["claim_id"],
                dispatch_id=c["dispatch_id"],
                proposal_id=c["proposal_id"],
                worker_id=c["worker_id"],
                lease_seconds=c["lease_seconds"],
                claimed_at=c["claimed_at"],
                expires_at=c["expires_at"],
                released=is_released,
                released_at=c.get("released_at"),
                settlement_status=c.get("settlement_status"),
                settled_at=c.get("settled_at"),
            )
            recent_claims.append(claim)
        
        # Sort by claimed_at descending and limit
        recent_claims.sort(key=lambda c: c.claimed_at, reverse=True)
        recent_claims = recent_claims[:recent_limit]
        
        has_changes = since_revision is None or self._revision > since_revision
        
        return ProposalFollowUpClaimSummary(
            claim_revision=self._revision,
            latest_change_at=self._latest_change_at,
            total_claims=len(filtered_claims),
            active_claims=active_count,
            expired_claims=expired_count,
            released_claims=released_count,
            settled_claims=settled_count,
            reassignable_claims=reassignable_count,
            by_worker=dict(sorted(by_worker.items(), key=lambda x: (-x[1], x[0]))),
            by_delivery_mode=dict(sorted(by_delivery_mode.items(), key=lambda x: (-x[1], x[0]))),
            recent_claims=recent_claims,
            has_changes=has_changes,
            since_revision=since_revision,
        )
    
    def get_revision(self) -> int:
        """Get current revision."""
        return self._revision


_proposal_follow_up_claim_store: Optional[ProposalFollowUpClaimStore] = None


def get_proposal_follow_up_claim_store() -> ProposalFollowUpClaimStore:
    """Get or create the proposal follow-up claim store."""
    global _proposal_follow_up_claim_store
    if _proposal_follow_up_claim_store is None:
        _proposal_follow_up_claim_store = ProposalFollowUpClaimStore()
    return _proposal_follow_up_claim_store
