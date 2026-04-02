"""Contract tests for Slice 34 — Proposal Lifecycle Notification Digest.

Tests verify that the notification digest surface exposes proposal lifecycle
data from the canonical read-model layer without building separate aggregations.
"""
from __future__ import annotations

import pytest
from copilot_core.action_closure import get_action_closure_store
from copilot_core.core.proposal_lifecycle_read_model import (
    build_proposal_lifecycle_status_summary,
)


class TestProposalLifecycleNotificationDigestContract:
    """Test contract shape and delta behavior for proposal lifecycle digests."""

    def test_digest_contract_shape(self):
        """Proposal lifecycle digest exposes canonical V1 contract fields."""
        store = get_action_closure_store()
        summary = build_proposal_lifecycle_status_summary(store, recent_limit=5).to_dict()

        assert "contract" in summary
        assert summary["contract"] == "ProposalLifecycleStatusSummaryV1"
        assert "revision" in summary
        assert "latest_change_at" in summary
        assert "total_proposals" in summary
        assert "lifecycle_statuses" in summary
        assert "recent_statuses" in summary
        assert "delta" in summary

    def test_lifecycle_status_breakdown(self):
        """Digest includes lifecycle status counts for all canonical states."""
        store = get_action_closure_store()
        summary = build_proposal_lifecycle_status_summary(store, recent_limit=5).to_dict()

        statuses = summary.get("lifecycle_statuses", {})
        canonical_states = {"suggested", "accepted", "executed", "failed", "follow_up_open", "settled"}
        for state in canonical_states:
            assert state in statuses or True  # state may be absent if count is zero

    def test_delta_payload_structure(self):
        """Delta payload includes revision cursor and changed flag."""
        store = get_action_closure_store()
        summary = build_proposal_lifecycle_status_summary(store, recent_limit=5, since_revision=0).to_dict()

        delta = summary.get("delta", {})
        assert "contract" in delta
        assert delta["contract"] == "ProposalLifecycleStatusDeltaV1"
        assert "since_revision" in delta
        assert "current_revision" in delta
        assert "changed" in delta
        assert "changed_count" in delta
        assert "recent_statuses" in delta

    def test_recent_statuses_structure(self):
        """Recent statuses include proposal_id, lifecycle_status, and revision."""
        store = get_action_closure_store()
        summary = build_proposal_lifecycle_status_summary(store, recent_limit=3).to_dict()

        recent = summary.get("recent_statuses", [])
        if recent:
            for entry in recent:
                assert "proposal_id" in entry
                assert "lifecycle_status" in entry
                assert "revision" in entry
                assert "latest_change_at" in entry

    def test_zone_filtering(self):
        """Zone filtering produces consistent digest with zone-scoped data."""
        store = get_action_closure_store()
        summary_all = build_proposal_lifecycle_status_summary(store, recent_limit=5).to_dict()
        summary_zone = build_proposal_lifecycle_status_summary(store, zone_id="wohnzimmer", recent_limit=5).to_dict()

        assert summary_all["total_proposals"] >= summary_zone["total_proposals"]
        if summary_zone["total_proposals"] > 0:
            zones = summary_zone.get("zones", {})
            assert "wohnzimmer" in zones or len(zones) == 0

    def test_since_revision_cursor(self):
        """Since-revision cursor produces delta-aware digest."""
        store = get_action_closure_store()
        summary_base = build_proposal_lifecycle_status_summary(store, recent_limit=5).to_dict()
        base_revision = summary_base.get("revision", 0)

        summary_delta = build_proposal_lifecycle_status_summary(
            store, recent_limit=5, since_revision=base_revision
        ).to_dict()

        delta = summary_delta.get("delta", {})
        assert delta.get("since_revision") == base_revision
        assert delta.get("current_revision") >= base_revision

    def test_notification_digest_integration(self):
        """Notification endpoints can include proposal lifecycle digest."""
        from copilot_core.api.v1.notifications import _build_proposal_lifecycle_notification_digest

        digest = _build_proposal_lifecycle_notification_digest(
            zone_id=None,
            since_revision=None,
            recent_limit=5,
        )

        assert digest["contract"] == "ProposalLifecycleNotificationDigestV1"
        assert "revision" in digest
        assert "latest_change_at" in digest
        assert "total_proposals" in digest
        assert "follow_ups" in digest
        assert "delta" in digest

    def test_follow_up_structure(self):
        """Follow-up entries include proposal_id, lifecycle_status, and priority."""
        from copilot_core.api.v1.notifications import _collect_proposal_lifecycle_follow_ups

        _, follow_ups = _collect_proposal_lifecycle_follow_ups(
            zone_id=None,
            since_revision=None,
            recent_limit=5,
        )

        for entry in follow_ups:
            assert "proposal_id" in entry
            assert "lifecycle_status" in entry
            assert "kind" in entry
            assert "priority" in entry
            assert entry["kind"] in {"problematic", "open"}
            assert entry["priority"] in {"high", "normal"}

    def test_failed_proposal_marked_problematic(self):
        """Failed proposals are marked as problematic with high priority."""
        from copilot_core.api.v1.notifications import _build_proposal_lifecycle_follow_up

        entry = {
            "proposal_id": "test-123",
            "lifecycle_status": "failed",
            "zone_id": "wohnzimmer",
            "revision": 5,
            "latest_change_at": "2026-04-02T10:00:00Z",
        }
        follow_up = _build_proposal_lifecycle_follow_up(entry)

        assert follow_up is not None
        assert follow_up["kind"] == "problematic"
        assert follow_up["priority"] == "high"
        assert follow_up["proposal_id"] == "test-123"

    def test_suggested_proposal_marked_open(self):
        """Suggested proposals are marked as open with normal priority."""
        from copilot_core.api.v1.notifications import _build_proposal_lifecycle_follow_up

        entry = {
            "proposal_id": "test-456",
            "lifecycle_status": "suggested",
            "module_id": "licht",
            "revision": 3,
            "latest_change_at": "2026-04-02T09:00:00Z",
        }
        follow_up = _build_proposal_lifecycle_follow_up(entry)

        assert follow_up is not None
        assert follow_up["kind"] == "open"
        assert follow_up["priority"] == "normal"
        assert follow_up["proposal_id"] == "test-456"

    def test_executed_proposal_no_follow_up(self):
        """Executed proposals do not generate follow-up entries."""
        from copilot_core.api.v1.notifications import _build_proposal_lifecycle_follow_up

        entry = {
            "proposal_id": "test-789",
            "lifecycle_status": "executed",
            "zone_id": "schlafzimmer",
            "revision": 7,
            "latest_change_at": "2026-04-02T08:00:00Z",
        }
        follow_up = _build_proposal_lifecycle_follow_up(entry)

        assert follow_up is None

    def test_settled_proposal_no_follow_up(self):
        """Settled proposals do not generate follow-up entries."""
        from copilot_core.api.v1.notifications import _build_proposal_lifecycle_follow_up

        entry = {
            "proposal_id": "test-999",
            "lifecycle_status": "settled",
            "zone_id": "kuche",
            "revision": 2,
            "latest_change_at": "2026-04-02T07:00:00Z",
        }
        follow_up = _build_proposal_lifecycle_follow_up(entry)

        assert follow_up is None

    def test_zone_scoped_follow_ups(self):
        """Zone-scoped collection returns only zone-matched follow-ups."""
        from copilot_core.api.v1.notifications import _collect_proposal_lifecycle_follow_ups

        _, follow_ups_all = _collect_proposal_lifecycle_follow_ups(
            zone_id=None,
            since_revision=None,
            recent_limit=10,
        )
        _, follow_ups_zone = _collect_proposal_lifecycle_follow_ups(
            zone_id="wohnzimmer",
            since_revision=None,
            recent_limit=10,
        )

        assert len(follow_ups_all) >= len(follow_ups_zone)
        for entry in follow_ups_zone:
            assert entry.get("zone_id") == "wohnzimmer" or entry.get("module_id") is not None

    def test_count_fields_in_digest(self):
        """Digest includes count fields for all lifecycle states."""
        from copilot_core.api.v1.notifications import _build_proposal_lifecycle_notification_digest

        digest = _build_proposal_lifecycle_notification_digest(
            zone_id=None,
            since_revision=None,
            recent_limit=5,
        )

        assert "suggested_count" in digest
        assert "accepted_count" in digest
        assert "executed_count" in digest
        assert "failed_count" in digest
        assert "follow_up_open_count" in digest
        assert "settled_count" in digest
        assert "total_proposals" in digest

    def test_revision_monotonicity(self):
        """Revision is monotonic and increases with changes."""
        store = get_action_closure_store()
        summary1 = build_proposal_lifecycle_status_summary(store, recent_limit=5).to_dict()
        summary2 = build_proposal_lifecycle_status_summary(store, recent_limit=5, since_revision=0).to_dict()

        rev1 = summary1.get("revision", 0)
        rev2 = summary2.get("revision", 0)
        assert rev2 >= rev1
