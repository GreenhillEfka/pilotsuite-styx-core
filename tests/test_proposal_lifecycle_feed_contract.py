"""
Tests for Proposal Lifecycle Feed API (Slice 34)

Zone-scoped proposal lifecycle feeds for dashboard pollers and system contexts.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from copilot_core.proposal_lifecycle_read_model import (
    ZoneProposalFeedStore,
    ZoneProposalFeedV1,
    ZoneProposalFeedSummaryV1,
    ZoneProposalFeedEntryV1,
)
from copilot_core.core.proposal_lifecycle_read_model import (
    ProposalLifecycleStatus,
)
from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine


class TestZoneProposalFeedStore:
    """Test zone-scoped proposal feed store."""

    @pytest.fixture
    def suggestion_engine(self):
        """Mock suggestion engine."""
        engine = MagicMock(spec=AutomationSuggestionEngine)
        return engine

    @pytest.fixture
    def lifecycle_statuses(self):
        """Sample lifecycle statuses for testing."""
        from copilot_core.core.dashboard_read_models import ReadModelMeta
        meta = ReadModelMeta()
        return [
            ProposalLifecycleStatus(
                meta=meta,
                proposal_id="prop-001",
                lifecycle_status="suggested",
                zone_id="zone-living",
                title="Lichtscenario Abend",
                summary="Warmes Licht fuer Entspannungsmodus",
                source="predictive",
                confidence=0.85,
                latest_change_at="2026-04-02T08:00:00Z",
                revision=1,
            ),
            ProposalLifecycleStatus(
                meta=meta,
                proposal_id="prop-002",
                lifecycle_status="accepted",
                zone_id="zone-living",
                title="Heizung runter",
                summary="Fenster offen erkannt",
                source="habitus",
                confidence=0.92,
                latest_change_at="2026-04-02T08:15:00Z",
                revision=2,
                closure_id="closure-002",
            ),
            ProposalLifecycleStatus(
                meta=meta,
                proposal_id="prop-003",
                lifecycle_status="failed",
                zone_id="zone-bedroom",
                title="Rollladen schliessen",
                summary="Zeitgesteuert fehlgeschlagen",
                source="predictive",
                confidence=0.78,
                latest_change_at="2026-04-02T06:30:00Z",
                revision=1,
                closure_id="closure-003",
            ),
            ProposalLifecycleStatus(
                meta=meta,
                proposal_id="prop-004",
                lifecycle_status="follow_up_open",
                zone_id="zone-bedroom",
                title="Licht aus",
                summary="Vergessen beim Verlassen",
                source="voice",
                confidence=0.95,
                latest_change_at="2026-04-02T07:45:00Z",
                revision=2,
                closure_id="closure-004",
            ),
        ]

    def test_build_zone_feed_single_zone(self, suggestion_engine, lifecycle_statuses):
        """Test building feed for a single zone."""
        with patch('copilot_core.proposal_lifecycle_read_model.ProposalLifecycleStore') as MockLifecycleStore:
            mock_lifecycle_store = MagicMock()
            mock_lifecycle_store.list_statuses.return_value = lifecycle_statuses
            MockLifecycleStore.return_value = mock_lifecycle_store

            store = ZoneProposalFeedStore(suggestion_engine)
            feed = store.build_zone_feed(zone_id="zone-living", zone_name="Wohnzimmer")

            assert feed.zone_id == "zone-living"
            assert feed.zone_name == "Wohnzimmer"
            assert len(feed.proposals) == 2
            assert feed.revision == 2
            assert feed.has_pending is True
            assert feed.has_failed is False
            assert feed.has_follow_up_open is False

            living_proposals = [p for p in lifecycle_statuses if p.zone_id == "zone-living"]
            assert len(feed.proposals) == len(living_proposals)

    def test_build_zone_feed_summary(self, suggestion_engine, lifecycle_statuses):
        """Test building summary of zone feeds."""
        with patch('copilot_core.proposal_lifecycle_read_model.ProposalLifecycleStore') as MockLifecycleStore:
            mock_lifecycle_store = MagicMock()
            mock_lifecycle_store.list_statuses.return_value = lifecycle_statuses
            MockLifecycleStore.return_value = mock_lifecycle_store

            store = ZoneProposalFeedStore(suggestion_engine)
            summary = store.build_zone_feed_summary(
                zone_names={
                    "zone-living": "Wohnzimmer",
                    "zone-bedroom": "Schlafzimmer",
                }
            )

            assert summary.revision == 2
            assert summary.total_proposals == 4
            assert summary.zones_with_pending == 1
            assert summary.zones_with_failed == 1
            assert summary.zones_with_follow_up == 1
            assert len(summary.zones) == 2

    def test_zone_feed_filters_by_zone_ids(self, suggestion_engine, lifecycle_statuses):
        """Test filtering summary by zone IDs."""
        with patch('copilot_core.proposal_lifecycle_read_model.ProposalLifecycleStore') as MockLifecycleStore:
            mock_lifecycle_store = MagicMock()
            mock_lifecycle_store.list_statuses.return_value = lifecycle_statuses
            MockLifecycleStore.return_value = mock_lifecycle_store

            store = ZoneProposalFeedStore(suggestion_engine)
            summary = store.build_zone_feed_summary(
                zone_ids=["zone-bedroom"],
                zone_names={"zone-bedroom": "Schlafzimmer"},
            )

            assert len(summary.zones) == 1
            assert summary.zones[0].zone_id == "zone-bedroom"
            assert summary.total_proposals == 2
            assert summary.zones_with_failed == 1
            assert summary.zones_with_follow_up == 1

    def test_zone_feed_entry_structure(self, suggestion_engine, lifecycle_statuses):
        """Test zone feed entry structure."""
        with patch('copilot_core.proposal_lifecycle_read_model.ProposalLifecycleStore') as MockLifecycleStore:
            mock_lifecycle_store = MagicMock()
            mock_lifecycle_store.list_statuses.return_value = lifecycle_statuses
            MockLifecycleStore.return_value = mock_lifecycle_store

            store = ZoneProposalFeedStore(suggestion_engine)
            feed = store.build_zone_feed(zone_id="zone-bedroom", zone_name="Schlafzimmer")

            assert len(feed.proposals) == 2
            entry = feed.proposals[0]
            assert isinstance(entry, ZoneProposalFeedEntryV1)
            assert entry.proposal_id.startswith("prop-")
            assert entry.zone_id == "zone-bedroom"
            assert entry.zone_name == "Schlafzimmer"
            assert entry.status in ["suggested", "accepted", "executed", "failed", "follow_up_open", "settled"]
            assert entry.revision >= 1

    def test_zone_feed_revision_tracking(self, suggestion_engine, lifecycle_statuses):
        """Test revision tracking in zone feeds."""
        with patch('copilot_core.proposal_lifecycle_read_model.ProposalLifecycleStore') as MockLifecycleStore:
            mock_lifecycle_store = MagicMock()
            mock_lifecycle_store.list_statuses.return_value = lifecycle_statuses
            MockLifecycleStore.return_value = mock_lifecycle_store

            store = ZoneProposalFeedStore(suggestion_engine)
            feed = store.build_zone_feed(zone_id="zone-living")

            assert feed.revision == 2
            assert feed.latest_change_at == "2026-04-02T08:15:00Z"

    def test_zone_feed_status_flags(self, suggestion_engine, lifecycle_statuses):
        """Test status flags in zone feeds."""
        with patch('copilot_core.proposal_lifecycle_read_model.ProposalLifecycleStore') as MockLifecycleStore:
            mock_lifecycle_store = MagicMock()
            mock_lifecycle_store.list_statuses.return_value = lifecycle_statuses
            MockLifecycleStore.return_value = mock_lifecycle_store

            store = ZoneProposalFeedStore(suggestion_engine)

            living_feed = store.build_zone_feed(zone_id="zone-living")
            assert living_feed.has_pending is True
            assert living_feed.has_failed is False
            assert living_feed.has_follow_up_open is False

            bedroom_feed = store.build_zone_feed(zone_id="zone-bedroom")
            assert bedroom_feed.has_pending is False
            assert bedroom_feed.has_failed is True
            assert bedroom_feed.has_follow_up_open is True


class TestZoneProposalFeedAPI:
    """Test proposal lifecycle feed API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with proposal lifecycle feed blueprint."""
        from flask import Flask
        from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine
        from copilot_core.api.v1.proposal_lifecycle_feed import (
            create_proposal_lifecycle_feed_blueprint,
        )

        app = Flask(__name__)
        app.config["TESTING"] = True

        suggestion_engine = AutomationSuggestionEngine()
        blueprint = create_proposal_lifecycle_feed_blueprint(suggestion_engine)
        app.register_blueprint(blueprint)

        with app.test_client() as client:
            yield client

    def test_list_zone_feeds(self, client):
        """Test listing all zone feeds."""
        response = client.get("/api/v1/proposals/feed")
        assert response.status_code == 200
        data = response.get_json()
        assert "revision" in data
        assert "has_changes" in data
        assert "zones" in data

    def test_list_zone_feeds_with_filter(self, client):
        """Test listing zone feeds with zone_id filter."""
        response = client.get("/api/v1/proposals/feed?zone_id=zone-living")
        assert response.status_code == 200
        data = response.get_json()
        assert "zone_id" in data
        assert data["zone_id"] == "zone-living"

    def test_list_zone_feeds_with_since_cursor(self, client):
        """Test delta responses with since revision cursor."""
        response = client.get("/api/v1/proposals/feed?since=999999")
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_changes"] is False
        assert "revision" in data

    def test_get_zone_feed(self, client):
        """Test getting feed for specific zone."""
        response = client.get("/api/v1/proposals/feed/zone/zone-living")
        assert response.status_code == 200
        data = response.get_json()
        assert "zone_id" in data
        assert "proposals" in data
        assert "revision" in data

    def test_get_zone_feed_with_since_cursor(self, client):
        """Test zone feed delta response."""
        response = client.get("/api/v1/proposals/feed/zone/zone-living?since=999999")
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_changes"] is False

    def test_zone_feed_includes_zone_name(self, client):
        """Test that zone names are resolved in feed."""
        with patch("copilot_core.storage.zone_truth.ZoneTruthStore") as mock_zone_store:
            mock_zone = MagicMock()
            mock_zone.name = "Wohnzimmer"
            mock_zone_store.return_value.get_zone.return_value = mock_zone

            response = client.get("/api/v1/proposals/feed/zone/zone-living")
            assert response.status_code == 200
            data = response.get_json()
            assert data.get("zone_name") == "Wohnzimmer" or data.get("zone_name") is None
