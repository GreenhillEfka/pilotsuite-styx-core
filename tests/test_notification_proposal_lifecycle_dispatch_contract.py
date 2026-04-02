"""Contract coverage for proposal lifecycle dispatch worker surfaces (Slice 35)."""

from __future__ import annotations

from pathlib import Path
import sys
from datetime import datetime, timezone
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.notifications import (  # noqa: E402
    ProposalLifecycleDispatchStore,
    get_proposal_lifecycle_dispatch_store,
)


def setup_function() -> None:
    """Reset stores before each test."""
    get_proposal_lifecycle_dispatch_store().clear()


def _seed_lifecycle_summary() -> dict[str, Any]:
    """Seed a mock lifecycle summary for dispatch testing."""
    return {
        "contract": "ProposalLifecycleStatusSummaryV1",
        "revision": 1,
        "latest_change_at": datetime.now(timezone.utc).isoformat(),
        "total_proposals": 3,
        "lifecycle_statuses": {"proposed": 1, "accepted": 1, "failed": 1},
        "sources": {"predictive": 1, "habitus": 1, "voice": 1},
        "zones": {"zone:living": 1, "zone:sleep": 1, "zone:kitchen": 1},
        "modules": {"light": 1, "climate": 1, "media": 1},
        "recent_statuses": [
            {
                "proposal_id": "proposal:living:light:1",
                "lifecycle_status": "proposed",
                "zone_id": "zone:living",
                "module_id": "light",
                "source": "predictive",
                "title": "Licht im Wohnzimmer einschalten",
                "summary": "Predictive Vorschlag basierend auf Anwesenheit",
                "confidence": 0.85,
                "revision": 1,
                "latest_change_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "proposal_id": "proposal:sleep:climate:1",
                "lifecycle_status": "accepted",
                "zone_id": "zone:sleep",
                "module_id": "climate",
                "source": "habitus",
                "title": "Heizung im Schlafzimmer anpassen",
                "summary": "Habitus-Regel: Nachtabsenkung",
                "confidence": 0.92,
                "accepted_at": datetime.now(timezone.utc).isoformat(),
                "revision": 2,
                "latest_change_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "proposal_id": "proposal:kitchen:media:1",
                "lifecycle_status": "failed",
                "zone_id": "zone:kitchen",
                "module_id": "media",
                "source": "voice",
                "title": "Musik in der Küche spielen",
                "summary": "Voice-Kommando fehlgeschlagen",
                "confidence": 0.78,
                "revision": 3,
                "latest_change_at": datetime.now(timezone.utc).isoformat(),
            },
        ],
        "highlights": [],
        "delta": {},
    }


def test_dispatch_store_materializes_candidates_from_lifecycle_summary() -> None:
    """Test that dispatch store materializes candidates from lifecycle summary."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    # Verify bundle structure
    assert bundle.delivery_mode == "notification_job"
    assert len(bundle.candidates) == 3
    
    # Verify cursor
    assert bundle.cursor.current_revision == 1
    assert bundle.cursor.candidate_count == 3
    
    # Verify counts
    bundle_dict = bundle.to_dict()
    assert bundle_dict["counts"]["dispatchable"] == 3
    assert "proposed" in bundle_dict["counts"]["by_status"]
    assert "accepted" in bundle_dict["counts"]["by_status"]
    assert "failed" in bundle_dict["counts"]["by_status"]


def test_dispatch_candidate_has_required_fields() -> None:
    """Test that dispatch candidates have all required fields."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    assert len(bundle.candidates) > 0
    candidate = bundle.candidates[0]
    
    # Verify required fields
    assert candidate.proposal_id is not None
    assert candidate.lifecycle_status is not None
    assert candidate.priority is not None
    assert candidate.delivery_mode is not None
    assert candidate.revision is not None
    
    # Verify candidate dict
    candidate_dict = candidate.to_dict()
    assert candidate_dict["contract"] == "ProposalLifecycleDispatchCandidateV1"
    assert "proposal_id" in candidate_dict
    assert "lifecycle_status" in candidate_dict
    assert "zone_id" in candidate_dict
    assert "module_id" in candidate_dict
    assert "source" in candidate_dict
    assert "title" in candidate_dict
    assert "summary" in candidate_dict


def test_store_tracks_candidates_internally() -> None:
    """Test that store tracks candidates internally after materialization."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    # Materialize candidates
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    # Verify candidates are stored
    assert len(store._candidates) == 3
    
    # Verify candidate structure
    for candidate_id, candidate_data in store._candidates.items():
        assert "candidate_id" in candidate_data
        assert "proposal_id" in candidate_data
        assert "delivery_mode" in candidate_data
        assert candidate_data["acknowledged"] is False
        assert candidate_data["claimed"] is False
        assert candidate_data["settled"] is False


def test_acknowledge_surface_tracks_worker_acknowledgements() -> None:
    """Test that acknowledge surface tracks worker acknowledgements."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    # Materialize candidates
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    # Get candidate_ids from internal store
    candidate_ids = list(store._candidates.keys())[:2]
    
    # Acknowledge
    acknowledgements = store.acknowledge(
        candidate_ids=candidate_ids,
        worker_id="worker-1",
    )
    
    assert len(acknowledgements) == len(candidate_ids)
    for ack in acknowledgements:
        assert "ack_id" in ack
        assert ack["worker_id"] == "worker-1"
    
    # Verify acknowledgements are stored
    assert len(store._acknowledgements) == len(candidate_ids)


def test_receipt_surface_materializes_delivery_outcomes() -> None:
    """Test that receipt surface materializes delivery outcomes."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    # Materialize
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    # Get candidate_ids
    candidate_ids = list(store._candidates.keys())[:2]
    
    # Record receipts
    receipts = [
        {
            "candidate_id": candidate_ids[0],
            "delivery_status": "delivered",
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "candidate_id": candidate_ids[1],
            "delivery_status": "failed",
            "error": "Notification service unavailable",
            "retry_count": 1,
        },
    ]
    
    recorded = store.record_receipts(receipts=receipts)
    assert len(recorded) == 2
    
    # Verify receipts are stored
    assert len(store._receipts) == 2
    
    # Verify receipt structure
    for receipt_id, receipt_data in store._receipts.items():
        assert "receipt_id" in receipt_data
        assert "candidate_id" in receipt_data
        assert "delivery_status" in receipt_data


def test_settle_surface_completes_dispatch_lifecycle() -> None:
    """Test that settle surface completes dispatch lifecycle."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    # Materialize
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    # Get candidate_ids and claim them first
    candidate_ids = list(store._candidates.keys())[:2]
    store.claim(candidate_ids=candidate_ids, worker_id="worker-1")
    
    # Settle
    settlements = [
        {
            "candidate_id": candidate_ids[0],
            "settlement_status": "completed",
            "outcome": "User viewed notification",
        },
        {
            "candidate_id": candidate_ids[1],
            "settlement_status": "abandoned",
            "outcome": "Notification expired",
        },
    ]
    
    settled, conflicts = store.settle_claims(settlements=settlements)
    assert len(settled) == 2
    assert len(conflicts) == 0
    
    # Verify settlements are stored
    assert len(store._settlements) == 2
    
    # Verify candidates are marked as settled
    for candidate_id in candidate_ids:
        assert store._candidates[candidate_id]["settled"] is True


def test_revision_tracking_enables_incremental_polling() -> None:
    """Test that revision tracking enables incremental polling."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    initial_revision = store.get_revision()
    assert initial_revision == 0
    
    # Materialize candidates (does NOT increment revision - only reads from summary)
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    # Revision should reflect the summary revision
    assert bundle.cursor.current_revision == seed["revision"]
    
    # Acknowledge should increment revision
    candidate_ids = list(store._candidates.keys())[:1]
    store.acknowledge(candidate_ids=candidate_ids, worker_id="worker-1")
    
    after_ack_revision = store.get_revision()
    assert after_ack_revision > 0


def test_priority_determination_based_on_lifecycle_status() -> None:
    """Test that priority is determined based on lifecycle status."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=10,
    )
    
    # Verify priority assignment
    for candidate in bundle.candidates:
        status = candidate.lifecycle_status
        priority = candidate.priority
        
        if status in {"failed", "rejected", "cancelled", "error"}:
            assert priority == "high", f"Failed status should have high priority, got {priority}"
        elif status in {"accepted", "pending", "queued"}:
            assert priority in {"normal", "high"}, f"Accepted status should have normal/high priority, got {priority}"
        elif status in {"proposed", "suggested"}:
            assert priority in {"low", "normal"}, f"Proposed status should have low/normal priority, got {priority}"


def test_delivery_mode_separation() -> None:
    """Test that delivery modes are tracked separately."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    # Materialize for notification_job
    bundle_notification = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    # Materialize for reminder_queue
    bundle_reminder = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="reminder_queue",
        recent_limit=5,
    )
    
    # Both should have same number of candidates
    assert len(bundle_notification.candidates) == len(bundle_reminder.candidates)
    
    # But delivery mode should be different
    for c in bundle_notification.candidates:
        assert c.delivery_mode == "notification_job"
    
    for c in bundle_reminder.candidates:
        assert c.delivery_mode == "reminder_queue"


def test_clear_resets_store_state() -> None:
    """Test that clear method resets store state."""
    seed = _seed_lifecycle_summary()
    store = get_proposal_lifecycle_dispatch_store()
    
    # Materialize and modify state
    bundle = store.materialize_candidates(
        lifecycle_summary=seed,
        delivery_mode="notification_job",
        recent_limit=5,
    )
    
    candidate_ids = list(store._candidates.keys())[:1]
    store.acknowledge(candidate_ids=candidate_ids, worker_id="worker-1")
    
    # Verify state is not empty
    assert len(store._candidates) > 0
    assert store.get_revision() > 0
    
    # Clear
    store.clear()
    
    # Verify state is reset
    assert len(store._candidates) == 0
    assert len(store._acknowledgements) == 0
    assert store.get_revision() == 0
