"""API contract tests for Proposal Follow-Up Claim / Lease Surface (Slice 38).

Tests verify:
1. POST /notifications/proposals/dispatch/claim - claim dispatch
2. GET /notifications/proposals/claims - get summary
3. GET /notifications/proposals/claims/<id> - get single claim
4. POST /notifications/proposals/claims/<id>/release - release claim
5. POST /notifications/proposals/claims/<id>/settle - settle claim
6. Claim conflict detection via API
"""
import pytest
import json

from flask import Flask
from copilot_core.core.proposal_follow_up_claim import get_proposal_follow_up_claim_store
from copilot_core.api.v1.proposal_claims import proposal_claims_bp


@pytest.fixture(autouse=True)
def clear_store():
    """Clear claim store before each test."""
    store = get_proposal_follow_up_claim_store()
    store.clear()
    yield


@pytest.fixture
def app():
    """Create test app with proposal claims blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(proposal_claims_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestProposalClaimsAPI:
    """Test proposal claims API endpoints."""
    
    def test_claim_dispatch(self, client):
        """Test POST /notifications/proposals/dispatch/claim."""
        response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_001",
                "proposal_id": "proposal_001",
                "worker_id": "worker_alpha",
                "lease_seconds": 300,
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 201
        data = response.get_json()
        
        assert data["contract"] == "ProposalFollowUpClaimV1"
        assert data["dispatch_id"] == "dispatch_001"
        assert data["proposal_id"] == "proposal_001"
        assert data["worker_id"] == "worker_alpha"
        assert data["lease_seconds"] == 300
        assert "claim_id" in data
    
    def test_claim_dispatch_missing_fields(self, client):
        """Test POST /notifications/proposals/dispatch/claim with missing fields."""
        response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_001",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_claim_dispatch_conflict(self, client):
        """Test claim conflict when already claimed."""
        # First claim
        client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_002",
                "proposal_id": "proposal_002",
                "worker_id": "worker_alpha",
            }),
            content_type="application/json",
        )
        
        # Second claim by different worker
        response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_002",
                "proposal_id": "proposal_002",
                "worker_id": "worker_beta",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "claim_conflict"
        assert data["conflict"]["reason"] == "already_claimed"
    
    def test_get_claims_summary(self, client):
        """Test GET /notifications/proposals/claims."""
        # Create some claims
        client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_003a",
                "proposal_id": "proposal_003a",
                "worker_id": "worker_gamma",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_003b",
                "proposal_id": "proposal_003b",
                "worker_id": "worker_gamma",
            }),
            content_type="application/json",
        )
        
        response = client.get("/notifications/proposals/claims")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["contract"] == "ProposalFollowUpClaimSummaryV1"
        assert data["total_claims"] == 2
        assert data["active_claims"] == 2
    
    def test_get_claims_summary_with_worker_filter(self, client):
        """Test GET /notifications/proposals/claims?worker_id=worker_gamma."""
        client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_004a",
                "proposal_id": "proposal_004a",
                "worker_id": "worker_gamma",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_004b",
                "proposal_id": "proposal_004b",
                "worker_id": "worker_delta",
            }),
            content_type="application/json",
        )
        
        response = client.get("/notifications/proposals/claims?worker_id=worker_gamma")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["total_claims"] == 1
        assert data["by_worker"] == {"worker_gamma": 1}
    
    def test_get_single_claim(self, client):
        """Test GET /notifications/proposals/claims/<claim_id>."""
        # First create a claim
        post_response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_005",
                "proposal_id": "proposal_005",
                "worker_id": "worker_epsilon",
            }),
            content_type="application/json",
        )
        claim_id = post_response.get_json()["claim_id"]
        
        response = client.get(f"/notifications/proposals/claims/{claim_id}")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["claim_id"] == claim_id
        assert data["worker_id"] == "worker_epsilon"
    
    def test_get_single_claim_not_found(self, client):
        """Test GET /notifications/proposals/claims/<id> for non-existent claim."""
        response = client.get("/notifications/proposals/claims/nonexistent")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
    
    def test_release_claim(self, client):
        """Test POST /notifications/proposals/claims/<id>/release."""
        # Create a claim
        post_response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_006",
                "proposal_id": "proposal_006",
                "worker_id": "worker_zeta",
            }),
            content_type="application/json",
        )
        claim_id = post_response.get_json()["claim_id"]
        
        # Release it
        response = client.post(
            f"/notifications/proposals/claims/{claim_id}/release",
            data=json.dumps({
                "worker_id": "worker_zeta",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["released"] is True
    
    def test_release_claim_wrong_worker(self, client):
        """Test release by wrong worker fails."""
        post_response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_007",
                "proposal_id": "proposal_007",
                "worker_id": "worker_eta",
            }),
            content_type="application/json",
        )
        claim_id = post_response.get_json()["claim_id"]
        
        response = client.post(
            f"/notifications/proposals/claims/{claim_id}/release",
            data=json.dumps({
                "worker_id": "worker_wrong",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 403
    
    def test_settle_claim(self, client):
        """Test POST /notifications/proposals/claims/<id>/settle."""
        post_response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_008",
                "proposal_id": "proposal_008",
                "worker_id": "worker_theta",
            }),
            content_type="application/json",
        )
        claim_id = post_response.get_json()["claim_id"]
        
        response = client.post(
            f"/notifications/proposals/claims/{claim_id}/settle",
            data=json.dumps({
                "worker_id": "worker_theta",
                "settlement_status": "completed",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["settled"] is True
        assert data["settlement_status"] == "completed"
    
    def test_settle_claim_abandoned(self, client):
        """Test settle claim as abandoned."""
        post_response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_009",
                "proposal_id": "proposal_009",
                "worker_id": "worker_iota",
            }),
            content_type="application/json",
        )
        claim_id = post_response.get_json()["claim_id"]
        
        response = client.post(
            f"/notifications/proposals/claims/{claim_id}/settle",
            data=json.dumps({
                "worker_id": "worker_iota",
                "settlement_status": "abandoned",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["settled"] is True
        assert data["settlement_status"] == "abandoned"
    
    def test_settle_claim_invalid_status(self, client):
        """Test settle with invalid status fails."""
        post_response = client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_010",
                "proposal_id": "proposal_010",
                "worker_id": "worker_kappa",
            }),
            content_type="application/json",
        )
        claim_id = post_response.get_json()["claim_id"]
        
        response = client.post(
            f"/notifications/proposals/claims/{claim_id}/settle",
            data=json.dumps({
                "worker_id": "worker_kappa",
                "settlement_status": "invalid_status",
            }),
            content_type="application/json",
        )
        
        assert response.status_code == 400
    
    def test_get_claims_by_worker(self, client):
        """Test GET /notifications/proposals/claims/worker/<worker_id>."""
        client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_011a",
                "proposal_id": "proposal_011a",
                "worker_id": "worker_lambda",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_011b",
                "proposal_id": "proposal_011b",
                "worker_id": "worker_lambda",
            }),
            content_type="application/json",
        )
        client.post(
            "/notifications/proposals/dispatch/claim",
            data=json.dumps({
                "dispatch_id": "dispatch_012",
                "proposal_id": "proposal_012",
                "worker_id": "worker_mu",
            }),
            content_type="application/json",
        )
        
        response = client.get("/notifications/proposals/claims/worker/worker_lambda")
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["worker_id"] == "worker_lambda"
        assert data["count"] == 2
        assert len(data["claims"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
