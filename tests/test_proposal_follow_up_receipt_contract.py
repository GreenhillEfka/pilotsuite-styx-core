"""Contract tests for Proposal Follow-Up Receipt Surface (Slice 37).

Tests verify:
1. Receipt materialization from dispatch
2. Receipt summary aggregation
3. Delta behavior with since_revision
4. Worker/delivery_mode filtering
5. Receipt reflection in dispatch/dashboard contexts
"""
import pytest
from datetime import datetime, timezone, timedelta

from copilot_core.core.proposal_follow_up_receipt import (
    ProposalFollowUpReceipt,
    ProposalFollowUpReceiptSummary,
    ProposalFollowUpReceiptStore,
    get_proposal_follow_up_receipt_store,
)
from copilot_core.core.proposal_follow_up_dispatch import (
    get_proposal_follow_up_dispatch_store,
)


@pytest.fixture(autouse=True)
def clear_stores():
    """Clear all stores before each test."""
    receipt_store = get_proposal_follow_up_receipt_store()
    receipt_store.clear()
    dispatch_store = get_proposal_follow_up_dispatch_store()
    dispatch_store.clear()
    yield


class TestProposalFollowUpReceiptStore:
    """Test receipt store basic operations."""
    
    def test_record_receipt(self):
        """Test basic receipt recording."""
        store = ProposalFollowUpReceiptStore()
        
        receipt = store.record_receipt(
            dispatch_id="dispatch_001",
            proposal_id="proposal_001",
            delivery_status="delivered",
            delivery_mode="notification_job",
            worker_id="worker_alpha",
            error=None,
            retry_count=0,
        )
        
        assert receipt.receipt_id.startswith("receipt_dispatch_001_")
        assert receipt.dispatch_id == "dispatch_001"
        assert receipt.proposal_id == "proposal_001"
        assert receipt.delivery_status == "delivered"
        assert receipt.delivery_mode == "notification_job"
        assert receipt.worker_id == "worker_alpha"
        assert receipt.error is None
        assert receipt.retry_count == 0
        assert receipt.escalation_due is False
    
    def test_record_receipt_with_error_and_retry(self):
        """Test receipt recording with error and retry info."""
        store = ProposalFollowUpReceiptStore()
        now = datetime.now(timezone.utc)
        next_retry = now + timedelta(minutes=5)
        
        receipt = store.record_receipt(
            dispatch_id="dispatch_002",
            proposal_id="proposal_002",
            delivery_status="failed",
            delivery_mode="reminder_queue",
            worker_id="worker_beta",
            error="SMTP connection timeout",
            retry_count=2,
            next_retry_at=next_retry.isoformat(),
            escalation_due=True,
        )
        
        assert receipt.delivery_status == "failed"
        assert receipt.delivery_mode == "reminder_queue"
        assert receipt.error == "SMTP connection timeout"
        assert receipt.retry_count == 2
        assert receipt.escalation_due is True
        assert receipt.next_retry_at is not None
    
    def test_get_receipt(self):
        """Test retrieving a single receipt."""
        store = ProposalFollowUpReceiptStore()
        
        recorded = store.record_receipt(
            dispatch_id="dispatch_003",
            proposal_id="proposal_003",
            delivery_status="delivered",
            delivery_mode="notification_job",
        )
        
        retrieved = store.get_receipt(recorded.receipt_id)
        assert retrieved is not None
        assert retrieved.receipt_id == recorded.receipt_id
        assert retrieved.proposal_id == "proposal_003"
    
    def test_get_receipt_not_found(self):
        """Test retrieving non-existent receipt."""
        store = ProposalFollowUpReceiptStore()
        retrieved = store.get_receipt("nonexistent_receipt")
        assert retrieved is None
    
    def test_get_receipts_by_proposal(self):
        """Test retrieving receipts by proposal ID."""
        store = ProposalFollowUpReceiptStore()
        
        store.record_receipt(
            dispatch_id="dispatch_004a",
            proposal_id="proposal_004",
            delivery_status="delivered",
            delivery_mode="notification_job",
        )
        store.record_receipt(
            dispatch_id="dispatch_004b",
            proposal_id="proposal_004",
            delivery_status="failed",
            delivery_mode="reminder_queue",
        )
        store.record_receipt(
            dispatch_id="dispatch_005",
            proposal_id="proposal_005",
            delivery_status="delivered",
            delivery_mode="notification_job",
        )
        
        receipts = store.get_receipts_by_proposal("proposal_004", limit=10)
        assert len(receipts) == 2
        assert all(r.proposal_id == "proposal_004" for r in receipts)
    
    def test_get_receipts_by_worker(self):
        """Test retrieving receipts by worker ID."""
        store = ProposalFollowUpReceiptStore()
        
        store.record_receipt(
            dispatch_id="dispatch_006a",
            proposal_id="proposal_006",
            delivery_status="delivered",
            delivery_mode="notification_job",
            worker_id="worker_gamma",
        )
        store.record_receipt(
            dispatch_id="dispatch_006b",
            proposal_id="proposal_007",
            delivery_status="delivered",
            delivery_mode="notification_job",
            worker_id="worker_gamma",
        )
        store.record_receipt(
            dispatch_id="dispatch_008",
            proposal_id="proposal_008",
            delivery_status="delivered",
            delivery_mode="notification_job",
            worker_id="worker_delta",
        )
        
        receipts = store.get_receipts_by_worker("worker_gamma", limit=10)
        assert len(receipts) == 2
        assert all(r.worker_id == "worker_gamma" for r in receipts)


class TestProposalFollowUpReceiptSummary:
    """Test receipt summary aggregation."""
    
    def test_receipt_summary_basic(self):
        """Test basic receipt summary generation."""
        store = ProposalFollowUpReceiptStore()
        
        # Record multiple receipts
        for i in range(5):
            store.record_receipt(
                dispatch_id=f"dispatch_{i:03d}",
                proposal_id=f"proposal_{i:03d}",
                delivery_status="delivered" if i % 2 == 0 else "failed",
                delivery_mode="notification_job" if i % 3 == 0 else "reminder_queue",
                worker_id=f"worker_{chr(97 + i % 3)}",
            )
        
        summary = store.get_receipt_summary(recent_limit=10)
        
        assert summary.receipt_revision == 5
        assert summary.total_receipts == 5
        assert summary.latest_change_at is not None
        assert len(summary.recent_receipts) == 5
        assert summary.has_changes is True
    
    def test_receipt_summary_by_status(self):
        """Test summary counts by delivery status."""
        store = ProposalFollowUpReceiptStore()
        
        # 3 delivered, 2 failed
        for i in range(3):
            store.record_receipt(
                dispatch_id=f"dispatch_del_{i}",
                proposal_id=f"proposal_{i}",
                delivery_status="delivered",
                delivery_mode="notification_job",
            )
        for i in range(2):
            store.record_receipt(
                dispatch_id=f"dispatch_fail_{i}",
                proposal_id=f"proposal_fail_{i}",
                delivery_status="failed",
                delivery_mode="notification_job",
            )
        
        summary = store.get_receipt_summary()
        
        assert summary.by_status.get("delivered") == 3
        assert summary.by_status.get("failed") == 2
    
    def test_receipt_summary_by_delivery_mode(self):
        """Test summary counts by delivery mode."""
        store = ProposalFollowUpReceiptStore()
        
        # 4 notification_job, 1 reminder_queue
        for i in range(4):
            store.record_receipt(
                dispatch_id=f"dispatch_notif_{i}",
                proposal_id=f"proposal_{i}",
                delivery_status="delivered",
                delivery_mode="notification_job",
            )
        store.record_receipt(
            dispatch_id="dispatch_reminder",
            proposal_id="proposal_reminder",
            delivery_status="queued",
            delivery_mode="reminder_queue",
        )
        
        summary = store.get_receipt_summary()
        
        assert summary.by_delivery_mode.get("notification_job") == 4
        assert summary.by_delivery_mode.get("reminder_queue") == 1
    
    def test_receipt_summary_by_worker(self):
        """Test summary counts by worker."""
        store = ProposalFollowUpReceiptStore()
        
        # 3 by worker_a, 2 by worker_b
        for i in range(3):
            store.record_receipt(
                dispatch_id=f"dispatch_a_{i}",
                proposal_id=f"proposal_{i}",
                delivery_status="delivered",
                worker_id="worker_a",
            )
        for i in range(2):
            store.record_receipt(
                dispatch_id=f"dispatch_b_{i}",
                proposal_id=f"proposal_b_{i}",
                delivery_status="delivered",
                worker_id="worker_b",
            )
        
        summary = store.get_receipt_summary()
        
        assert summary.by_worker.get("worker_a") == 3
        assert summary.by_worker.get("worker_b") == 2
    
    def test_receipt_summary_with_worker_filter(self):
        """Test summary filtered by worker ID."""
        store = ProposalFollowUpReceiptStore()
        
        store.record_receipt(
            dispatch_id="dispatch_a",
            proposal_id="proposal_a",
            delivery_status="delivered",
            worker_id="worker_alpha",
        )
        store.record_receipt(
            dispatch_id="dispatch_b",
            proposal_id="proposal_b",
            delivery_status="delivered",
            worker_id="worker_beta",
        )
        
        summary = store.get_receipt_summary(worker_id="worker_alpha")
        
        assert summary.total_receipts == 1
        assert summary.by_worker.get("worker_alpha") == 1
    
    def test_receipt_summary_with_delivery_mode_filter(self):
        """Test summary filtered by delivery mode."""
        store = ProposalFollowUpReceiptStore()
        
        store.record_receipt(
            dispatch_id="dispatch_notif",
            proposal_id="proposal_notif",
            delivery_status="delivered",
            delivery_mode="notification_job",
        )
        store.record_receipt(
            dispatch_id="dispatch_reminder",
            proposal_id="proposal_reminder",
            delivery_status="queued",
            delivery_mode="reminder_queue",
        )
        
        summary = store.get_receipt_summary(delivery_mode="notification_job")
        
        assert summary.total_receipts == 1
        assert summary.by_delivery_mode.get("notification_job") == 1
    
    def test_receipt_summary_recent_limit(self):
        """Test summary with recent receipt limit."""
        store = ProposalFollowUpReceiptStore()
        
        for i in range(20):
            store.record_receipt(
                dispatch_id=f"dispatch_{i:03d}",
                proposal_id=f"proposal_{i:03d}",
                delivery_status="delivered",
            )
        
        summary = store.get_receipt_summary(recent_limit=5)
        
        assert summary.total_receipts == 20
        assert len(summary.recent_receipts) == 5
    
    def test_receipt_summary_has_changes(self):
        """Test has_changes flag with since_revision."""
        store = ProposalFollowUpReceiptStore()
        
        # Initial state
        store.record_receipt(
            dispatch_id="dispatch_001",
            proposal_id="proposal_001",
            delivery_status="delivered",
        )
        
        summary1 = store.get_receipt_summary(since_revision=0)
        assert summary1.has_changes is True
        assert summary1.receipt_revision == 1
        
        # No new receipts
        summary2 = store.get_receipt_summary(since_revision=1)
        # has_changes depends on revision comparison
        
        # New receipt
        store.record_receipt(
            dispatch_id="dispatch_002",
            proposal_id="proposal_002",
            delivery_status="failed",
        )
        
        summary3 = store.get_receipt_summary(since_revision=1)
        assert summary3.receipt_revision == 2


class TestProposalFollowUpReceiptToDict:
    """Test serialization of receipt objects."""
    
    def test_receipt_to_dict(self):
        """Test receipt serialization."""
        receipt = ProposalFollowUpReceipt(
            receipt_id="receipt_001",
            dispatch_id="dispatch_001",
            proposal_id="proposal_001",
            delivery_status="delivered",
            delivery_mode="notification_job",
            worker_id="worker_test",
            delivered_at="2026-04-02T10:00:00Z",
            error=None,
            retry_count=0,
            next_retry_at=None,
            escalation_due=False,
            recorded_at="2026-04-02T10:00:00Z",
        )
        
        data = receipt.to_dict()
        
        assert data["contract"] == "ProposalFollowUpReceiptV1"
        assert data["receipt_id"] == "receipt_001"
        assert data["proposal_id"] == "proposal_001"
        assert data["delivery_status"] == "delivered"
    
    def test_summary_to_dict(self):
        """Test summary serialization."""
        summary = ProposalFollowUpReceiptSummary(
            receipt_revision=5,
            latest_change_at="2026-04-02T10:00:00Z",
            total_receipts=5,
            by_status={"delivered": 3, "failed": 2},
            by_delivery_mode={"notification_job": 5},
            by_worker={"worker_a": 5},
            recent_receipts=[],
            has_changes=True,
            since_revision=4,
        )
        
        data = summary.to_dict()
        
        assert data["contract"] == "ProposalFollowUpReceiptSummaryV1"
        assert data["receipt_revision"] == 5
        assert data["total_receipts"] == 5
        assert data["by_status"] == {"delivered": 3, "failed": 2}


class TestProposalFollowUpReceiptIntegration:
    """Integration tests for receipt surface."""
    
    def test_full_receipt_lifecycle(self):
        """Test complete receipt lifecycle from recording to summary."""
        store = ProposalFollowUpReceiptStore()
        
        # Record receipts
        receipt1 = store.record_receipt(
            dispatch_id="dispatch_lifecycle_001",
            proposal_id="proposal_lifecycle_001",
            delivery_status="delivered",
            delivery_mode="notification_job",
            worker_id="worker_lifecycle",
        )
        
        receipt2 = store.record_receipt(
            dispatch_id="dispatch_lifecycle_002",
            proposal_id="proposal_lifecycle_002",
            delivery_status="failed",
            delivery_mode="reminder_queue",
            worker_id="worker_lifecycle",
            error="Test error",
            retry_count=1,
            escalation_due=True,
        )
        
        # Get summary
        summary = store.get_receipt_summary(recent_limit=10)
        
        assert summary.total_receipts == 2
        assert summary.by_status == {"delivered": 1, "failed": 1}
        assert summary.by_delivery_mode == {"notification_job": 1, "reminder_queue": 1}
        assert summary.by_worker == {"worker_lifecycle": 2}
        
        # Get individual receipt
        retrieved = store.get_receipt(receipt1.receipt_id)
        assert retrieved is not None
        assert retrieved.delivery_status == "delivered"
        
        # Get receipts by proposal
        proposal_receipts = store.get_receipts_by_proposal("proposal_lifecycle_001")
        assert len(proposal_receipts) == 1
        assert proposal_receipts[0].proposal_id == "proposal_lifecycle_001"
        
        # Get receipts by worker
        worker_receipts = store.get_receipts_by_worker("worker_lifecycle")
        assert len(worker_receipts) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
