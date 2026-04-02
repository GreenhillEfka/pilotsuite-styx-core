"""Contract-Tests für Hold Analytics Surface."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from copilot_core.presence.hold_analytics import (
    HoldAnalyticsStore,
    HoldUsageEntryV1,
    HoldUsageHistoryV1,
    HoldZonePatternEntryV1,
    HoldZonePatternsV1,
    HoldEffectivenessMetricsV1,
    HoldAnalyticsSummaryV1,
)


class MockHoldStore:
    """Mock Hold Store für Tests."""

    def __init__(self, holds):
        self.holds = holds

    def get_all_holds(self):
        return self.holds


class MockZoneTruthStore:
    """Mock Zone Truth Store für Tests."""

    def __init__(self, zone_names):
        self.zone_names = zone_names

    def get_zone_name(self, zone_id):
        return self.zone_names.get(zone_id, f"Zone {zone_id}")


def create_mock_hold(
    hold_id,
    zone_id,
    hold_state="force_on",
    reason="manual_override",
    set_at=None,
    released_at=None,
    duration_seconds=None,
    expires_at=None,
):
    """Helper zum Erstellen von Mock Holds."""
    if set_at is None:
        set_at = datetime.now(timezone.utc).isoformat()

    hold = Mock()
    hold.hold_id = hold_id
    hold.zone_id = zone_id
    hold.hold_state = hold_state
    hold.reason = reason
    hold.set_at = set_at
    hold.released_at = released_at
    hold.duration_seconds = duration_seconds
    hold.expires_at = expires_at
    return hold


class TestHoldUsageHistory:
    """Tests für Hold-Usage-Historie."""

    def test_build_usage_history_empty(self):
        hold_store = MockHoldStore([])
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_usage_history()

        assert isinstance(result, HoldUsageHistoryV1)
        assert result.total_holds == 0
        assert result.entries == []
        assert result.revision == 1

    def test_build_usage_history_with_holds(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", "manual", set_at=(now - timedelta(hours=2)).isoformat()),
            create_mock_hold("h2", "zone_2", "force_off", "auto_expire", set_at=(now - timedelta(hours=1)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({"zone_1": "Wohnzimmer", "zone_2": "Schlafzimmer"})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_usage_history()

        assert result.total_holds == 2
        assert result.total_force_on == 1
        assert result.total_force_off == 1
        assert len(result.entries) == 2

    def test_build_usage_history_zone_filter(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", set_at=(now - timedelta(hours=2)).isoformat()),
            create_mock_hold("h2", "zone_2", "force_off", set_at=(now - timedelta(hours=1)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_usage_history(zone_id="zone_1")

        assert result.total_holds == 1
        assert result.entries[0].zone_id == "zone_1"

    def test_build_usage_history_with_duration(self):
        now = datetime.now(timezone.utc)
        set_at = (now - timedelta(hours=2)).isoformat()
        released_at = (now - timedelta(hours=1)).isoformat()

        holds = [
            create_mock_hold("h1", "zone_1", "force_on", set_at=set_at, released_at=released_at),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store=hold_store)

        result = analytics.build_usage_history()

        # Duration is released_at - set_at = 1 hour = 3600 seconds
        assert result.entries[0].actual_duration_seconds == 3600
        assert result.avg_duration_seconds == 3600.0

    def test_build_usage_history_revision_bump(self):
        hold_store = MockHoldStore([])
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        r1 = analytics.build_usage_history()
        r2 = analytics.build_usage_history()
        r3 = analytics.build_usage_history()

        assert r1.revision < r2.revision < r3.revision


class TestHoldZonePatterns:
    """Tests für Zone-spezifische Hold-Patterns."""

    def test_build_zone_patterns_empty(self):
        hold_store = MockHoldStore([])
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_zone_patterns()

        assert isinstance(result, HoldZonePatternsV1)
        assert result.total_zones == 0
        assert result.patterns == []

    def test_build_zone_patterns_single_zone(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", "manual", set_at=(now - timedelta(hours=2)).isoformat()),
            create_mock_hold("h2", "zone_1", "force_on", "manual", set_at=(now - timedelta(hours=1)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({"zone_1": "Wohnzimmer"})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_zone_patterns()

        assert result.total_zones == 1
        assert result.zones_with_holds == 1
        assert result.patterns[0].zone_id == "zone_1"
        assert result.patterns[0].zone_name == "Wohnzimmer"
        assert result.patterns[0].total_holds == 2
        assert result.patterns[0].force_on_count == 2

    def test_build_zone_patterns_multiple_zones(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", set_at=(now - timedelta(hours=3)).isoformat()),
            create_mock_hold("h2", "zone_2", "force_off", set_at=(now - timedelta(hours=2)).isoformat()),
            create_mock_hold("h3", "zone_3", "auto", set_at=(now - timedelta(hours=1)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_zone_patterns()

        assert result.total_zones == 3
        assert result.patterns[0].total_holds >= result.patterns[1].total_holds

    def test_build_zone_patterns_time_buckets(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", set_at=(now - timedelta(days=3)).isoformat()),
            create_mock_hold("h2", "zone_1", "force_on", set_at=(now - timedelta(days=10)).isoformat()),
            create_mock_hold("h3", "zone_1", "force_on", set_at=(now - timedelta(days=45)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_zone_patterns()

        assert result.patterns[0].holds_last_7_days == 1
        assert result.patterns[0].holds_last_30_days == 2


class TestHoldEffectivenessMetrics:
    """Tests für Hold-Effectiveness-Metriken."""

    def test_build_effectiveness_metrics_empty(self):
        hold_store = MockHoldStore([])
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store=hold_store)

        result = analytics.build_effectiveness_metrics()

        assert isinstance(result, HoldEffectivenessMetricsV1)
        assert result.total_holds_analyzed == 0
        assert result.conflict_rate == 0.0
        assert result.flapping_prevention_rate == 0.0
        # effectiveness_score = flapping_prevention_rate * 0.7 + (1.0 - conflict_rate) * 0.3
        # With 0 holds: 0.0 * 0.7 + (1.0 - 0.0) * 0.3 = 0.3
        assert result.effectiveness_score == 0.3

    def test_build_effectiveness_metrics_with_force_holds(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", set_at=(now - timedelta(hours=2)).isoformat()),
            create_mock_hold("h2", "zone_2", "force_off", set_at=(now - timedelta(hours=1)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_effectiveness_metrics()

        assert result.total_holds_analyzed == 2
        assert result.holds_preventing_flapping == 2
        assert result.flapping_prevention_rate == 1.0
        assert result.zones_benefiting_from_holds == 2

    def test_build_effectiveness_metrics_mixed_states(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", set_at=(now - timedelta(hours=2)).isoformat()),
            create_mock_hold("h2", "zone_2", "auto", set_at=(now - timedelta(hours=1)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_effectiveness_metrics()

        assert result.total_holds_analyzed == 2
        assert result.holds_preventing_flapping == 1
        assert result.flapping_prevention_rate == 0.5
        assert result.zones_benefiting_from_holds == 1
        assert result.zones_without_benefit == 1

    def test_build_effectiveness_metrics_effectiveness_score(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", set_at=(now - timedelta(hours=2)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_effectiveness_metrics()

        assert result.effectiveness_score >= 0.0
        assert result.effectiveness_score <= 1.0


class TestHoldAnalyticsSummary:
    """Tests für vollständige Analytics-Summary."""

    def test_build_summary(self):
        now = datetime.now(timezone.utc)
        holds = [
            create_mock_hold("h1", "zone_1", "force_on", set_at=(now - timedelta(hours=2)).isoformat()),
            create_mock_hold("h2", "zone_2", "force_off", set_at=(now - timedelta(hours=1)).isoformat()),
        ]

        hold_store = MockHoldStore(holds)
        zone_store = MockZoneTruthStore({"zone_1": "Wohnzimmer", "zone_2": "Schlafzimmer"})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        result = analytics.build_summary()

        assert isinstance(result, HoldAnalyticsSummaryV1)
        assert isinstance(result.usage, HoldUsageHistoryV1)
        assert isinstance(result.patterns, HoldZonePatternsV1)
        assert isinstance(result.effectiveness, HoldEffectivenessMetricsV1)
        assert result.summary_revision >= 1

    def test_build_summary_revision_independence(self):
        hold_store = MockHoldStore([])
        zone_store = MockZoneTruthStore({})
        analytics = HoldAnalyticsStore(hold_store, None, zone_store)

        s1 = analytics.build_summary()
        s2 = analytics.build_summary()

        assert s1.summary_revision < s2.summary_revision


class TestHoldUsageEntryV1:
    """Tests für HoldUsageEntryV1 Dataclass."""

    def test_entry_creation(self):
        entry = HoldUsageEntryV1(
            hold_id="h1",
            zone_id="zone_1",
            hold_state="force_on",
            reason="manual",
            set_at="2026-04-02T12:00:00Z",
            released_at="2026-04-02T14:00:00Z",
            duration_seconds=7200,
            actual_duration_seconds=7200,
            expiration_reason="manual_release",
        )

        assert entry.hold_id == "h1"
        assert entry.zone_id == "zone_1"
        assert entry.hold_state == "force_on"
        assert entry.actual_duration_seconds == 7200

    def test_entry_immutability(self):
        entry = HoldUsageEntryV1(
            hold_id="h1",
            zone_id="zone_1",
            hold_state="force_on",
            reason=None,
            set_at="2026-04-02T12:00:00Z",
            released_at=None,
            duration_seconds=None,
            actual_duration_seconds=None,
            expiration_reason=None,
        )

        with pytest.raises(Exception):
            entry.hold_id = "h2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
