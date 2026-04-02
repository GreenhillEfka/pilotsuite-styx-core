"""API contract tests for Proposal Follow-Up Receipt Surface (Slice 37).

Tests verify:
1. POST /notifications/proposals/receipt - record receipt
2. GET /notifications/proposals/receipts - get summary
3. GET /notifications/proposals/receipts/<id> - get single receipt
4. GET /notifications/proposals/receipts/proposal/<id> - get by proposal
5. GET /notifications/proposals/receipts/worker/<id> - get by worker
6. Delta behavior with since_revision
"""
import pytest
import json
from datetime import datetime, timezone

from flask import Flask
from copilot_core.core.proposal_follow_up_receipt import get_proposal_follow_up_receipt_store
from copilot_core.api.v1.proposal_receipts import proposal_receipts_bp


@pytest.fixture(autouse=True)
def clear_store():
    """Clear receipt store before each test."""
    store = get_proposal_follow_up_receipt_store()
    store.clear()
    yield


@pytest.fixture
def app():
    """Create test app with proposal receipts blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(proposal_receipts_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestProposalReceiptAPI:
    """Test proposal receipt API endpoints."""
    
    def test_record_receipt(self, client):
        """Test POST /notifications/proposals/receipt."""
        response = client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_001",
                "proposal_id": "proposal_001",
                "delivery_status": "delivered",
                "delivery_mode": "notification_job",
                "worker_id": "worker_alpha",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 201
        data = response.get_json()
        
        assert data["contract"] == "ProposalFollowUpReceiptV1"
        assert data["dispatch_id"] == "dispatch_001"
        assert data["proposal_id"] == "proposal_001"
        assert data["delivery_status"] == "delivered"
        assert data["delivery_mode"] == "notification_job"
        assert data["worker_id"] == "worker_alpha"
        assert "receipt_id" in data
    
    def test_record_receipt_with_error(self, client):
        """Test POST /notifications/proposals/receipt with error/retry."""
        response = client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_002",
                "proposal_id": "proposal_002",
                "delivery_status": "failed",
                "delivery_mode": "reminder_queue",
                "worker_id": "worker_beta",
                "error": "SMTP timeout",
                "retry_count": 2,
                "escalation_due": True,
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 201
        data = response.get_json()
        
        assert data["delivery_status"] == "failed"
        assert data["error"] == "SMTP timeout"
        assert data["retry_count"] == 2
        assert data["escalation_due"] is True
    
    def test_record_receipt_missing_fields(self, client):
        """Test POST /notifications/proposals/receipt with missing required fields."""
        response = client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "delivery_status": "delivered",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_get_receipts_summary(self, client):
        """Test GET /notifications/proposals/receipts."""
        # First record some receipts
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_001",
                "proposal_id": "proposal_001",
                "delivery_status": "delivered",
                "delivery_mode": "notification_job",
                "worker_id": "worker_alpha",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_002",
                "proposal_id": "proposal_002",
                "delivery_status": "failed",
                "delivery_mode": "reminder_queue",
                "worker_id": "worker_beta",
            }),
            content_type="application/json",
        )
        
        response = client.get("/notifications/proposals/receipts")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["contract"] == "ProposalFollowUpReceiptSummaryV1"
        assert data["total_receipts"] == 2
        assert data["by_status"] == {"delivered": 1, "failed": 1}
        assert data["by_delivery_mode"] == {"notification_job": 1, "reminder_queue": 1}
        assert len(data["recent_receipts"]) == 2
    
    def test_get_receipts_summary_with_worker_filter(self, client):
        """Test GET /notifications/proposals/receipts?worker_id=worker_alpha."""
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_001",
                "proposal_id": "proposal_001",
                "delivery_status": "delivered",
                "worker_id": "worker_alpha",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_002",
                "proposal_id": "proposal_002",
                "delivery_status": "delivered",
                "worker_id": "worker_beta",
            }),
            content_type="application/json",
        )
        
        response = client.get("/notifications/proposals/receipts?worker_id=worker_alpha")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["total_receipts"] == 1
        assert data["by_worker"] == {"worker_alpha": 1}
    
    def test_get_receipts_summary_with_delivery_mode_filter(self, client):
        """Test GET /notifications/proposals/receipts?delivery_mode=notification_job."""
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_001",
                "proposal_id": "proposal_001",
                "delivery_status": "delivered",
                "delivery_mode": "notification_job",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_002",
                "proposal_id": "proposal_002",
                "delivery_status": "queued",
                "delivery_mode": "reminder_queue",
            }),
            content_type="application/json",
        )
        
        response = client.get("/notifications/proposals/receipts?delivery_mode=notification_job")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["total_receipts"] == 1
        assert data["by_delivery_mode"] == {"notification_job": 1}
    
    def test_get_receipts_summary_with_since_revision(self, client):
        """Test GET /notifications/proposals/receipts?since_revision=1."""
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_001",
                "proposal_id": "proposal_001",
                "delivery_status": "delivered",
            }),
            content_type="application/json",
        )
        
        response1 = client.get("/notifications/proposals/receipts?since_revision=0")
        assert response1.status_code == 200
        data1 = response1.get_json()
        assert data1["receipt_revision"] == 1
        
        response2 = client.get("/notifications/proposals/receipts?since_revision=1")
        assert response2.status_code == 200
        data2 = response2.get_json()
        assert data2["receipt_revision"] == 1
    
    def test_get_single_receipt(self, client):
        """Test GET /notifications/proposals/receipts/<receipt_id>."""
        # First record a receipt
        post_response = client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_003",
                "proposal_id": "proposal_003",
                "delivery_status": "delivered",
            }),
            content_type="application/json",
        )
        receipt_id = post_response.get_json()["receipt_id"]
        
        response = client.get(f"/notifications/proposals/receipts/{receipt_id}")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["receipt_id"] == receipt_id
        assert data["proposal_id"] == "proposal_003"
    
    def test_get_single_receipt_not_found(self, client):
        """Test GET /notifications/proposals/receipts/<id> for non-existent receipt."""
        response = client.get("/notifications/proposals/receipts/nonexistent")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
    
    def test_get_receipts_by_proposal(self, client):
        """Test GET /notifications/proposals/receipts/proposal/<proposal_id>."""
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_004a",
                "proposal_id": "proposal_004",
                "delivery_status": "delivered",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_004b",
                "proposal_id": "proposal_004",
                "delivery_status": "failed",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_005",
                "proposal_id": "proposal_005",
                "delivery_status": "delivered",
            }),
            content_type="application/json",
        )
        
        response = client.get("/notifications/proposals/receipts/proposal/proposal_004")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["proposal_id"] == "proposal_004"
        assert data["count"] == 2
        assert len(data["receipts"]) == 2
    
    def test_get_receipts_by_worker(self, client):
        """Test GET /notifications/proposals/receipts/worker/<worker_id>."""
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_006a",
                "proposal_id": "proposal_006",
                "delivery_status": "delivered",
                "worker_id": "worker_gamma",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_006b",
                "proposal_id": "proposal_007",
                "delivery_status": "delivered",
                "worker_id": "worker_gamma",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/receipt",
            data=json.dumps({
                "dispatch_id": "dispatch_008",
                "proposal_id": "proposal_008",
                "delivery_status": "delivered",
                "worker_id": "worker_delta",
            }),
            content_type="application/json",
        )
        
        response = client.get("/notifications/proposals/receipts/worker/worker_gamma")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["worker_id"] == "worker_gamma"
        assert data["count"] == 2
        assert len(data["receipts"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
