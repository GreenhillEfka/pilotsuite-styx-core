"""Contract coverage for proposal follow-up dispatch worker (Slice 36)."""

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


from copilot_core.core.proposal_follow_up_dispatch import (  # noqa: E402
    ProposalFollowUpDispatchStore,
    get_proposal_follow_up_dispatch_store,
)


def setup_function() -> None:
    """Reset stores before each test."""
    get_proposal_follow_up_dispatch_store().clear()


def _seed_dispatch_bundle() -> dict[str, Any]:
    """Seed a mock dispatch bundle for follow-up testing."""
    return {
        "contract": "ProposalLifecycleDispatchV1",
        "delivery_mode": "notification_job",
        "cursor": {
            "contract": "ProposalLifecycleDispatchCursorV1",
            "since_revision": None,
            "current_revision": 1,
            "has_changes": True,
            "latest_change_at": datetime.now(timezone.utc).isoformat(),
            "candidate_count": 3,
        },
        "counts": {
            "dispatchable": 3,
            "by_status": {"proposed": 1, "accepted": 1, "failed": 1},
            "by_source": {"predictive": 1, "habitus": 1, "voice": 1},
        },
        "candidates": [
            {
                "contract": "ProposalLifecycleDispatchCandidateV1",
                "proposal_id": "proposal:living:light:1",
                "lifecycle_status": "proposed",
                "zone_id": "zone:living",
                "module_id": "light",
                "source": "predictive",
                "title": "Licht im Wohnzimmer einschalten",
                "summary": "Predictive Vorschlag basierend auf Anwesenheit",
                "priority": "low",
                "delivery_mode": "notification_job",
                "revision": 1,
            },
            {
                "contract": "ProposalLifecycleDispatchCandidateV1",
                "proposal_id": "proposal:sleep:climate:1",
                "lifecycle_status": "accepted",
                "zone_id": "zone:sleep",
                "module_id": "climate",
                "source": "habitus",
                "title": "Heizung im Schlafzimmer anpassen",
                "summary": "Habitus-Regel: Nachtabsenkung",
                "priority": "normal",
                "delivery_mode": "notification_job",
                "revision": 2,
            },
            {
                "contract": "ProposalLifecycleDispatchCandidateV1",
                "proposal_id": "proposal:kitchen:media:1",
                "lifecycle_status": "failed",
                "zone_id": "zone:kitchen",
                "module_id": "media",
                "source": "voice",
                "title": "Musik in der Küche spielen",
                "summary": "Voice-Kommando fehlgeschlagen",
                "priority": "high",
                "delivery_mode": "notification_job",
                "revision": 3,
            },
        ],
    }


def test_follow_up_store_materializes_from_dispatch_bundle() -> None:
    """Test that follow-up store materializes candidates from dispatch bundle."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    # Verify bundle structure
    assert bundle.delivery_mode == "notification_job"
    assert len(bundle.candidates) == 3
    
    # Verify cursor
    assert bundle.cursor.current_revision == 1
    assert bundle.cursor.candidate_count == 3
    assert bundle.cursor.has_changes is True
    
    # Verify counts
    bundle_dict = bundle.to_dict()
    assert bundle_dict["counts"]["dispatchable"] == 3
    assert "by_status" in bundle_dict["counts"]
    assert "by_source" in bundle_dict["counts"]
    assert "by_priority" in bundle_dict["counts"]


def test_follow_up_candidate_has_required_fields() -> None:
    """Test that follow-up candidates have all required fields."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    assert len(bundle.candidates) > 0
    candidate = bundle.candidates[0]
    
    # Verify required fields
    assert candidate.proposal_id is not None
    assert candidate.lifecycle_status is not None
    assert candidate.dispatch_id is not None
    assert candidate.delivery_mode is not None
    assert candidate.created_at is not None
    
    # Verify candidate dict
    candidate_dict = candidate.to_dict()
    assert candidate_dict["contract"] == "ProposalFollowUpDispatchCandidateV1"
    assert "proposal_id" in candidate_dict
    assert "lifecycle_status" in candidate_dict
    assert "dispatch_id" in candidate_dict
    assert "zone_id" in candidate_dict
    assert "module_id" in candidate_dict
    assert "source" in candidate_dict
    assert "title" in candidate_dict
    assert "summary" in candidate_dict
    assert "priority" in candidate_dict


def test_store_tracks_candidates_internally() -> None:
    """Test that store tracks candidates internally after materialization."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    # Materialize candidates
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    # Verify candidates are stored
    assert len(store._candidates) == 3
    
    # Verify candidate structure
    for dispatch_id, candidate_data in store._candidates.items():
        assert "dispatch_id" in candidate_data
        assert "proposal_id" in candidate_data
        assert "delivery_mode" in candidate_data
        assert candidate_data["acknowledged"] is False
        assert candidate_data["delivered"] is False


def test_acknowledge_surface_tracks_worker_acknowledgements() -> None:
    """Test that acknowledge surface tracks worker acknowledgements."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    # Materialize candidates
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    # Get dispatch_ids from internal store
    dispatch_ids = list(store._candidates.keys())[:2]
    
    # Acknowledge
    acknowledgements = store.acknowledge(
        dispatch_ids=dispatch_ids,
        worker_id="worker-1",
    )
    
    assert len(acknowledgements) == len(dispatch_ids)
    for ack in acknowledgements:
        assert "ack_id" in ack
        assert ack["worker_id"] == "worker-1"
        assert ack["dispatch_id"] in dispatch_ids
    
    # Verify acknowledgements are stored
    assert len(store._acks) == len(dispatch_ids)
    
    # Verify candidates are marked as acknowledged
    for dispatch_id in dispatch_ids:
        assert store._candidates[dispatch_id]["acknowledged"] is True
        assert store._candidates[dispatch_id]["ack_worker_id"] == "worker-1"


def test_receipt_surface_materializes_delivery_outcomes() -> None:
    """Test that receipt surface materializes delivery outcomes."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    # Materialize
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    # Get dispatch_ids
    dispatch_ids = list(store._candidates.keys())[:2]
    
    # Record receipts
    receipts = [
        {
            "dispatch_id": dispatch_ids[0],
            "delivery_status": "delivered",
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "dispatch_id": dispatch_ids[1],
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
        assert "dispatch_id" in receipt_data
        assert "delivery_status" in receipt_data
    
    # Verify delivered flag is set correctly
    assert store._candidates[dispatch_ids[0]]["delivered"] is True
    assert store._candidates[dispatch_ids[1]]["delivered"] is False


def test_revision_tracking_enables_incremental_polling() -> None:
    """Test that revision tracking enables incremental polling."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    initial_revision = store.get_revision()
    assert initial_revision == 0
    
    # Materialize (does NOT increment revision)
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    # Acknowledge should increment revision
    dispatch_ids = list(store._candidates.keys())[:1]
    store.acknowledge(dispatch_ids=dispatch_ids, worker_id="worker-1")
    
    after_ack_revision = store.get_revision()
    assert after_ack_revision > 0
    
    # Record receipt should increment revision
    receipts = [
        {
            "dispatch_id": dispatch_ids[0],
            "delivery_status": "delivered",
        },
    ]
    store.record_receipts(receipts=receipts)
    
    after_receipt_revision = store.get_revision()
    assert after_receipt_revision > after_ack_revision


def test_pending_ack_count_tracking() -> None:
    """Test that pending acknowledgement count is tracked."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    # Materialize
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    # All candidates pending ack
    assert store.get_pending_ack_count() == 3
    
    # Acknowledge some
    dispatch_ids = list(store._candidates.keys())[:2]
    store.acknowledge(dispatch_ids=dispatch_ids, worker_id="worker-1")
    
    # One remaining
    assert store.get_pending_ack_count() == 1
    
    # Acknowledge all
    all_dispatch_ids = list(store._candidates.keys())
    store.acknowledge(dispatch_ids=all_dispatch_ids, worker_id="worker-1")
    
    # None pending
    assert store.get_pending_ack_count() == 0


def test_cursor_includes_pending_ack_count() -> None:
    """Test that cursor includes pending acknowledgement count."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    # Materialize
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    # All pending
    assert bundle.cursor.pending_ack_count == 3
    
    # Acknowledge some
    dispatch_ids = list(store._candidates.keys())[:2]
    store.acknowledge(dispatch_ids=dispatch_ids, worker_id="worker-1")
    
    # Re-materialize to get updated cursor
    bundle2 = store.materialize_from_dispatch_bundle(seed)
    assert bundle2.cursor.pending_ack_count == 1


def test_clear_resets_store_state() -> None:
    """Test that clear method resets store state."""
    seed = _seed_dispatch_bundle()
    store = get_proposal_follow_up_dispatch_store()
    
    # Materialize and modify state
    bundle = store.materialize_from_dispatch_bundle(seed)
    
    dispatch_ids = list(store._candidates.keys())[:1]
    store.acknowledge(dispatch_ids=dispatch_ids, worker_id="worker-1")
    
    # Verify state is not empty
    assert len(store._candidates) > 0
    assert len(store._acks) > 0
    assert store.get_revision() > 0
    
    # Clear
    store.clear()
    
    # Verify state is reset
    assert len(store._candidates) == 0
    assert len(store._acks) == 0
    assert len(store._receipts) == 0
    assert store.get_revision() == 0
    assert store.get_pending_ack_count() == 0


def test_delivery_mode_preservation() -> None:
    """Test that delivery mode is preserved through materialization."""
    seed_notification = _seed_dispatch_bundle()
    seed_notification["delivery_mode"] = "notification_job"
    
    seed_reminder = _seed_dispatch_bundle()
    seed_reminder["delivery_mode"] = "reminder_queue"
    
    store = get_proposal_follow_up_dispatch_store()
    
    # Materialize for notification_job
    bundle_notification = store.materialize_from_dispatch_bundle(seed_notification)
    assert bundle_notification.delivery_mode == "notification_job"
    for c in bundle_notification.candidates:
        assert c.delivery_mode == "notification_job"
    
    # Clear and materialize for reminder_queue
    store.clear()
    bundle_reminder = store.materialize_from_dispatch_bundle(seed_reminder)
    assert bundle_reminder.delivery_mode == "reminder_queue"
    for c in bundle_reminder.candidates:
        assert c.delivery_mode == "reminder_queue"
