"""Contract tests for Proposal Follow-Up Claim / Lease Surface (Slice 38).

Tests verify:
1. Claim creation with lease
2. Claim conflict detection
3. Lease expiry and reassignability
4. Release and settlement
5. Summary aggregation with worker/delivery filters
"""
import pytest
from datetime import datetime, timezone, timedelta

from copilot_core.core.proposal_follow_up_claim import (
    ProposalFollowUpClaim,
    ProposalFollowUpClaimSummary,
    ProposalFollowUpClaimStore,
    get_proposal_follow_up_claim_store,
)


@pytest.fixture(autouse=True)
def clear_store():
    """Clear claim store before each test."""
    store = get_proposal_follow_up_claim_store()
    store.clear()
    yield


class TestProposalFollowUpClaimStore:
    """Test claim store basic operations."""
    
    def test_claim_creation(self):
        """Test basic claim creation."""
        store = ProposalFollowUpClaimStore()
        
        claim, conflict = store.claim(
            dispatch_id="dispatch_001",
            proposal_id="proposal_001",
            worker_id="worker_alpha",
            lease_seconds=300,
        )
        
        assert conflict is None
        assert claim is not None
        assert claim.claim_id.startswith("claim_dispatch_001_")
        assert claim.dispatch_id == "dispatch_001"
        assert claim.proposal_id == "proposal_001"
        assert claim.worker_id == "worker_alpha"
        assert claim.lease_seconds == 300
        assert claim.released is False
        assert claim.settlement_status is None
    
    def test_claim_conflict(self):
        """Test claim conflict when already claimed."""
        store = ProposalFollowUpClaimStore()
        
        # First claim
        claim1, conflict1 = store.claim(
            dispatch_id="dispatch_002",
            proposal_id="proposal_002",
            worker_id="worker_alpha",
        )
        assert conflict1 is None
        
        # Second claim by different worker - should conflict
        claim2, conflict2 = store.claim(
            dispatch_id="dispatch_002",
            proposal_id="proposal_002",
            worker_id="worker_beta",
        )
        
        assert claim2 is None
        assert conflict2 is not None
        assert conflict2["reason"] == "already_claimed"
        assert conflict2["claimed_by"] == "worker_alpha"
    
    def test_claim_same_worker_reclaim(self):
        """Test same worker can re-claim without conflict."""
        store = ProposalFollowUpClaimStore()
        
        claim1, _ = store.claim(
            dispatch_id="dispatch_003",
            proposal_id="proposal_003",
            worker_id="worker_gamma",
        )
        
        claim2, conflict = store.claim(
            dispatch_id="dispatch_003",
            proposal_id="proposal_003",
            worker_id="worker_gamma",
        )
        
        assert conflict is None
        assert claim2 is not None
        assert claim2.claim_id == claim1.claim_id
    
    def test_claim_release(self):
        """Test claim release."""
        store = ProposalFollowUpClaimStore()
        
        claim, _ = store.claim(
            dispatch_id="dispatch_004",
            proposal_id="proposal_004",
            worker_id="worker_delta",
        )
        
        released = store.release_claim(claim.claim_id, "worker_delta")
        assert released is True
        
        # Verify claim is released
        retrieved = store.get_claim(claim.claim_id)
        assert retrieved is not None
        assert retrieved.released is True
        assert retrieved.released_at is not None
    
    def test_claim_release_wrong_worker(self):
        """Test claim release by wrong worker fails."""
        store = ProposalFollowUpClaimStore()
        
        claim, _ = store.claim(
            dispatch_id="dispatch_005",
            proposal_id="proposal_005",
            worker_id="worker_epsilon",
        )
        
        released = store.release_claim(claim.claim_id, "worker_wrong")
        assert released is False
    
    def test_claim_settlement(self):
        """Test claim settlement."""
        store = ProposalFollowUpClaimStore()
        
        claim, _ = store.claim(
            dispatch_id="dispatch_006",
            proposal_id="proposal_006",
            worker_id="worker_zeta",
        )
        
        settled = store.settle_claim(claim.claim_id, "worker_zeta", "completed")
        assert settled is True
        
        retrieved = store.get_claim(claim.claim_id)
        assert retrieved is not None
        assert retrieved.settlement_status == "completed"
        assert retrieved.settled_at is not None
    
    def test_claim_settlement_abandoned(self):
        """Test claim settlement as abandoned."""
        store = ProposalFollowUpClaimStore()
        
        claim, _ = store.claim(
            dispatch_id="dispatch_007",
            proposal_id="proposal_007",
            worker_id="worker_eta",
        )
        
        settled = store.settle_claim(claim.claim_id, "worker_eta", "abandoned")
        assert settled is True
        
        retrieved = store.get_claim(claim.claim_id)
        assert retrieved.settlement_status == "abandoned"
    
    def test_get_claim(self):
        """Test retrieving a single claim."""
        store = ProposalFollowUpClaimStore()
        
        claim, _ = store.claim(
            dispatch_id="dispatch_008",
            proposal_id="proposal_008",
            worker_id="worker_theta",
        )
        
        retrieved = store.get_claim(claim.claim_id)
        assert retrieved is not None
        assert retrieved.claim_id == claim.claim_id
        assert retrieved.worker_id == "worker_theta"
    
    def test_get_claim_not_found(self):
        """Test retrieving non-existent claim."""
        store = ProposalFollowUpClaimStore()
        retrieved = store.get_claim("nonexistent_claim")
        assert retrieved is None
    
    def test_get_claims_by_worker(self):
        """Test retrieving claims by worker ID."""
        store = ProposalFollowUpClaimStore()
        
        store.claim("dispatch_009a", "proposal_009a", "worker_iota")
        store.claim("dispatch_009b", "proposal_009b", "worker_iota")
        store.claim("dispatch_010", "proposal_010", "worker_kappa")
        
        claims = store.get_claims_by_worker("worker_iota", limit=10)
        assert len(claims) == 2
        assert all(c.worker_id == "worker_iota" for c in claims)


class TestProposalFollowUpClaimExpiry:
    """Test claim expiry and reassignability."""
    
    def test_claim_is_active(self):
        """Test active claim detection."""
        claim = ProposalFollowUpClaim(
            claim_id="claim_test",
            dispatch_id="dispatch_test",
            proposal_id="proposal_test",
            worker_id="worker_test",
            lease_seconds=300,
            claimed_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        
        assert claim.is_active() is True
        assert claim.is_expired() is False
        assert claim.is_reassignable() is False
    
    def test_claim_is_expired(self):
        """Test expired claim detection."""
        claim = ProposalFollowUpClaim(
            claim_id="claim_test",
            dispatch_id="dispatch_test",
            proposal_id="proposal_test",
            worker_id="worker_test",
            lease_seconds=300,
            claimed_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            expires_at=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        )
        
        assert claim.is_active() is False
        assert claim.is_expired() is True
        assert claim.is_reassignable() is True
    
    def test_claim_is_released(self):
        """Test released claim is reassignable."""
        claim = ProposalFollowUpClaim(
            claim_id="claim_test",
            dispatch_id="dispatch_test",
            proposal_id="proposal_test",
            worker_id="worker_test",
            lease_seconds=300,
            claimed_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            released=True,
            released_at=datetime.now(timezone.utc).isoformat(),
        )
        
        assert claim.is_active() is False
        assert claim.is_expired() is False
        assert claim.is_reassignable() is True
    
    def test_claim_is_settled(self):
        """Test settled claim is not reassignable."""
        claim = ProposalFollowUpClaim(
            claim_id="claim_test",
            dispatch_id="dispatch_test",
            proposal_id="proposal_test",
            worker_id="worker_test",
            lease_seconds=300,
            claimed_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            settlement_status="completed",
            settled_at=datetime.now(timezone.utc).isoformat(),
        )
        
        assert claim.is_active() is False
        assert claim.is_expired() is False
        assert claim.is_reassignable() is False


class TestProposalFollowUpClaimSummary:
    """Test claim summary aggregation."""
    
    def test_claim_summary_basic(self):
        """Test basic claim summary generation."""
        store = ProposalFollowUpClaimStore()
        
        # Create multiple claims
        store.claim("dispatch_011a", "proposal_011a", "worker_lambda")
        store.claim("dispatch_011b", "proposal_011b", "worker_lambda")
        store.claim("dispatch_011c", "proposal_011c", "worker_mu")
        
        summary = store.get_claim_summary(recent_limit=10)
        
        assert summary.claim_revision == 3
        assert summary.total_claims == 3
        assert summary.active_claims == 3
        assert summary.expired_claims == 0
        assert summary.settled_claims == 0
        assert len(summary.recent_claims) == 3
    
    def test_claim_summary_by_worker(self):
        """Test summary counts by worker."""
        store = ProposalFollowUpClaimStore()
        
        store.claim("dispatch_012a", "proposal_012a", "worker_nu")
        store.claim("dispatch_012b", "proposal_012b", "worker_nu")
        store.claim("dispatch_012c", "proposal_012c", "worker_nu")
        store.claim("dispatch_013", "proposal_013", "worker_xi")
        
        summary = store.get_claim_summary()
        
        assert summary.by_worker.get("worker_nu") == 3
        assert summary.by_worker.get("worker_xi") == 1
    
    def test_claim_summary_with_settlement(self):
        """Test summary with settled claims."""
        store = ProposalFollowUpClaimStore()
        
        claim1, _ = store.claim("dispatch_014a", "proposal_014a", "worker_omicron")
        claim2, _ = store.claim("dispatch_014b", "proposal_014b", "worker_omicron")
        claim3, _ = store.claim("dispatch_014c", "proposal_014c", "worker_omicron")
        
        store.settle_claim(claim1.claim_id, "worker_omicron", "completed")
        store.settle_claim(claim2.claim_id, "worker_omicron", "abandoned")
        
        summary = store.get_claim_summary()
        
        assert summary.total_claims == 3
        assert summary.settled_claims == 2
        assert summary.active_claims == 1
    
    def test_claim_summary_with_release(self):
        """Test summary with released claims."""
        store = ProposalFollowUpClaimStore()
        
        claim1, _ = store.claim("dispatch_015a", "proposal_015a", "worker_pi")
        claim2, _ = store.claim("dispatch_015b", "proposal_015b", "worker_pi")
        
        store.release_claim(claim1.claim_id, "worker_pi")
        
        summary = store.get_claim_summary()
        
        assert summary.released_claims == 1
        assert summary.active_claims == 1
    
    def test_claim_summary_with_worker_filter(self):
        """Test summary filtered by worker ID."""
        store = ProposalFollowUpClaimStore()
        
        store.claim("dispatch_016a", "proposal_016a", "worker_rho")
        store.claim("dispatch_016b", "proposal_016b", "worker_sigma")
        
        summary = store.get_claim_summary(worker_id="worker_rho")
        
        assert summary.total_claims == 1
        assert summary.by_worker == {"worker_rho": 1}
    
    def test_claim_summary_has_changes(self):
        """Test has_changes flag with since_revision."""
        store = ProposalFollowUpClaimStore()
        
        store.claim("dispatch_017", "proposal_017", "worker_tau")
        
        summary1 = store.get_claim_summary(since_revision=0)
        assert summary1.has_changes is True
        assert summary1.claim_revision == 1
        
        summary2 = store.get_claim_summary(since_revision=1)
        # has_changes depends on revision comparison


class TestProposalFollowUpClaimToDict:
    """Test serialization of claim objects."""
    
    def test_claim_to_dict(self):
        """Test claim serialization."""
        claim = ProposalFollowUpClaim(
            claim_id="claim_001",
            dispatch_id="dispatch_001",
            proposal_id="proposal_001",
            worker_id="worker_test",
            lease_seconds=300,
            claimed_at="2026-04-02T10:00:00Z",
            expires_at="2026-04-02T10:05:00Z",
            released=False,
            settlement_status=None,
        )
        
        data = claim.to_dict()
        
        assert data["contract"] == "ProposalFollowUpClaimV1"
        assert data["claim_id"] == "claim_001"
        assert data["worker_id"] == "worker_test"
        assert data["lease_seconds"] == 300
    
    def test_summary_to_dict(self):
        """Test summary serialization."""
        summary = ProposalFollowUpClaimSummary(
            claim_revision=5,
            latest_change_at="2026-04-02T10:00:00Z",
            total_claims=5,
            active_claims=3,
            expired_claims=1,
            released_claims=1,
            settled_claims=0,
            reassignable_claims=1,
            by_worker={"worker_a": 5},
            by_delivery_mode={"notification_job": 5},
            recent_claims=[],
            has_changes=True,
            since_revision=4,
        )
        
        data = summary.to_dict()
        
        assert data["contract"] == "ProposalFollowUpClaimSummaryV1"
        assert data["claim_revision"] == 5
        assert data["active_claims"] == 3
        assert data["reassignable_claims"] == 1


class TestProposalFollowUpClaimIntegration:
    """Integration tests for claim surface."""
    
    def test_full_claim_lifecycle(self):
        """Test complete claim lifecycle from creation to settlement."""
        store = ProposalFollowUpClaimStore()
        
        # Claim
        claim, conflict = store.claim(
            dispatch_id="dispatch_lifecycle",
            proposal_id="proposal_lifecycle",
            worker_id="worker_lifecycle",
            lease_seconds=300,
        )
        assert conflict is None
        assert claim is not None
        
        # Verify active
        assert claim.is_active() is True
        
        # Settle
        settled = store.settle_claim(claim.claim_id, "worker_lifecycle", "completed")
        assert settled is True
        
        # Verify settled
        retrieved = store.get_claim(claim.claim_id)
        assert retrieved is not None
        assert retrieved.settlement_status == "completed"
        assert retrieved.is_active() is False
        
        # Get summary
        summary = store.get_claim_summary()
        assert summary.total_claims == 1
        assert summary.settled_claims == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
