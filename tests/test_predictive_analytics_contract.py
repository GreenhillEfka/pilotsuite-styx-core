"""Contract tests for Predictive Analytics — Slice 48."""
import pytest
from datetime import datetime, timezone, timedelta
import tempfile
import shutil
import os

from copilot_core.predictive.analytics import (
    PredictiveUsageEntryV1,
    PredictiveUsageHistoryV1,
    PredictiveZonePatternEntryV1,
    PredictiveZonePatternsV1,
    PredictiveEffectivenessMetricsV1,
    PredictiveTrendEntryV1,
    PredictiveTrendsV1,
    PredictiveAnalyticsSummaryV1,
)
from copilot_core.predictive.analytics_store import PredictiveAnalyticsStore


class TestPredictiveAnalyticsReadModels:
    """Test predictive analytics read models."""

    def test_usage_entry_creation(self):
        """Test predictive usage entry creation."""
        entry = PredictiveUsageEntryV1(
            proposal_id="prop-001",
            pattern_id="pattern-01",
            zone_id="zone_living",
            module_id="light",
            prediction_type="time_based",
            confidence_score=0.85,
            outcome="accepted",
            accepted_at=datetime.now(timezone.utc).isoformat(),
            rejected_at=None,
            expired_at=None,
            feedback=None,
        )

        assert entry.proposal_id == "prop-001"
        assert entry.confidence_score == 0.85
        assert entry.outcome == "accepted"
        assert entry.prediction_type == "time_based"
        assert entry.created_at is not None

    def test_usage_history_aggregation(self):
        """Test usage history aggregation."""
        entries = [
            PredictiveUsageEntryV1(
                proposal_id=f"prop-{i}",
                pattern_id="pattern-01",
                zone_id="zone_living",
                module_id="light",
                prediction_type="time_based",
                confidence_score=0.7 + (i * 0.05),
                outcome=["accepted", "rejected", "pending"][i % 3],
                accepted_at=datetime.now(timezone.utc).isoformat() if i % 3 == 0 else None,
                rejected_at=datetime.now(timezone.utc).isoformat() if i % 3 == 1 else None,
                expired_at=None,
                feedback=None,
            )
            for i in range(10)
        ]

        history = PredictiveUsageHistoryV1(
            entries=entries,
            total_proposals=len(entries),
            total_accepted=sum(1 for e in entries if e.outcome == "accepted"),
            total_rejected=sum(1 for e in entries if e.outcome == "rejected"),
            total_expired=sum(1 for e in entries if e.outcome == "expired"),
            total_pending=sum(1 for e in entries if e.outcome == "pending"),
            acceptance_rate=sum(1 for e in entries if e.outcome == "accepted") / len(entries),
            avg_confidence_score=sum(e.confidence_score for e in entries) / len(entries),
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert history.total_proposals == 10
        assert history.total_accepted == 4  # 0, 3, 6, 9
        assert history.total_rejected == 3  # 1, 4, 7
        assert history.total_pending == 3  # 2, 5, 8
        assert history.acceptance_rate == 0.4
        assert 0.7 <= history.avg_confidence_score <= 1.0

    def test_zone_pattern_entry(self):
        """Test zone pattern entry creation."""
        pattern = PredictiveZonePatternEntryV1(
            zone_id="zone_living",
            zone_name="Living Room",
            total_proposals=20,
            accepted_count=12,
            rejected_count=5,
            expired_count=3,
            acceptance_rate=0.6,
            avg_confidence_score=0.75,
            most_common_prediction_type="time_based",
            last_proposal_at=datetime.now(timezone.utc).isoformat(),
            proposals_last_7_days=5,
            proposals_last_30_days=20,
            dominant_pattern_ids=["pattern-01", "pattern-02"],
        )

        assert pattern.zone_id == "zone_living"
        assert pattern.acceptance_rate == 0.6
        assert pattern.accepted_count + pattern.rejected_count + pattern.expired_count == pattern.total_proposals

    def test_zone_patterns_aggregation(self):
        """Test zone patterns aggregation."""
        patterns = [
            PredictiveZonePatternEntryV1(
                zone_id=f"zone_{i}",
                zone_name=f"Zone {i}",
                total_proposals=10,
                accepted_count=6,
                rejected_count=3,
                expired_count=1,
                acceptance_rate=0.6,
                avg_confidence_score=0.7,
                most_common_prediction_type="time_based",
                last_proposal_at=datetime.now(timezone.utc).isoformat(),
                proposals_last_7_days=3,
                proposals_last_30_days=10,
                dominant_pattern_ids=["pattern-01"],
            )
            for i in range(4)
        ]

        zone_patterns = PredictiveZonePatternsV1(
            patterns=patterns,
            total_zones=len(patterns),
            zones_with_proposals=sum(1 for p in patterns if p.total_proposals > 0),
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert zone_patterns.total_zones == 4
        assert zone_patterns.zones_with_proposals == 4

    def test_effectiveness_metrics(self):
        """Test effectiveness metrics creation."""
        metrics = PredictiveEffectivenessMetricsV1(
            total_proposals_analyzed=100,
            high_confidence_proposals=40,  # confidence >= 0.8
            high_confidence_acceptance_rate=0.85,
            low_confidence_proposals=20,  # confidence < 0.4
            low_confidence_acceptance_rate=0.35,
            avg_time_to_accept_minutes=12.5,
            avg_time_to_reject_minutes=5.2,
            pattern_reinforcement_count=25,
            pattern_degradation_count=8,
            seasonal_adaptation_events=3,
            effectiveness_score=0.78,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert metrics.total_proposals_analyzed == 100
        assert metrics.effectiveness_score == 0.78
        assert metrics.high_confidence_acceptance_rate > metrics.low_confidence_acceptance_rate

    def test_trend_entry(self):
        """Test trend entry creation."""
        entry = PredictiveTrendEntryV1(
            period="daily",
            timestamp=datetime.now(timezone.utc).isoformat(),
            proposals_count=15,
            accepted_count=10,
            rejected_count=3,
            avg_confidence=0.75,
            acceptance_rate=0.67,
        )

        assert entry.period == "daily"
        assert entry.acceptance_rate == 0.67
        assert entry.proposals_count == entry.accepted_count + entry.rejected_count + 2  # pending/expired

    def test_trends_aggregation(self):
        """Test trends aggregation."""
        trends = [
            PredictiveTrendEntryV1(
                period="daily",
                timestamp=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                proposals_count=10 + i,
                accepted_count=6 + i,
                rejected_count=2,
                avg_confidence=0.6 + (i * 0.02),
                acceptance_rate=0.5 + (i * 0.03),
            )
            for i in range(7)
        ]

        trends_model = PredictiveTrendsV1(
            trends=trends,
            period="daily",
            total_periods=len(trends),
            trend_direction="improving",
            trend_slope=0.21,  # 0.71 - 0.5
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert trends_model.total_periods == 7
        assert trends_model.trend_direction == "improving"

    def test_analytics_summary(self):
        """Test analytics summary composition."""
        usage = PredictiveUsageHistoryV1(
            entries=[],
            total_proposals=50,
            total_accepted=30,
            total_rejected=15,
            total_expired=3,
            total_pending=2,
            acceptance_rate=0.6,
            avg_confidence_score=0.72,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        patterns = PredictiveZonePatternsV1(
            patterns=[],
            total_zones=5,
            zones_with_proposals=4,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        effectiveness = PredictiveEffectivenessMetricsV1(
            total_proposals_analyzed=50,
            high_confidence_proposals=20,
            high_confidence_acceptance_rate=0.8,
            low_confidence_proposals=10,
            low_confidence_acceptance_rate=0.4,
            avg_time_to_accept_minutes=10.0,
            avg_time_to_reject_minutes=5.0,
            pattern_reinforcement_count=15,
            pattern_degradation_count=5,
            seasonal_adaptation_events=2,
            effectiveness_score=0.75,
            revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        summary = PredictiveAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=1,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

        assert summary.summary_revision == 1
        assert summary.usage.acceptance_rate == 0.6
        assert summary.patterns.total_zones == 5
        assert summary.effectiveness.effectiveness_score == 0.75


class TestPredictiveAnalyticsStore:
    """Test Predictive Analytics Store."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for tests."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_predictive_analytics.db")
        yield db_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def store(self, temp_db):
        """Create store with temporary database."""
        return PredictiveAnalyticsStore(db_path=temp_db)

    def test_init_creates_tables(self, store):
        """Test store initialization creates required tables."""
        # If store initialized without error, tables were created
        assert store.db_path.endswith(".db")

    def test_add_usage_entry(self, store):
        """Test adding usage entry."""
        entry = PredictiveUsageEntryV1(
            proposal_id="prop-001",
            pattern_id="pattern-01",
            zone_id="zone_living",
            module_id="light",
            prediction_type="time_based",
            confidence_score=0.85,
            outcome="accepted",
            accepted_at=datetime.now(timezone.utc).isoformat(),
            rejected_at=None,
            expired_at=None,
            feedback=None,
        )

        store.add_usage_entry(entry)

        # Verify by reading back
        history = store.build_usage_history(zone_id="zone_living")
        assert history.total_proposals == 1
        assert history.total_accepted == 1
        assert history.acceptance_rate == 1.0
        assert len(history.entries) == 1
        assert history.entries[0].proposal_id == "prop-001"

    def test_build_usage_history(self, store):
        """Test building usage history."""
        # Add multiple entries
        base_time = datetime.now(timezone.utc) - timedelta(days=10)
        for i in range(20):
            entry = PredictiveUsageEntryV1(
                proposal_id=f"prop-{i:03d}",
                pattern_id=f"pattern-{i % 5:02d}",
                zone_id=f"zone-{i % 4:02d}",
                module_id=f"module-{i % 3:02d}",
                prediction_type=["time_based", "presence_based", "calendar_based", "seasonal", "behavioral"][i % 5],
                confidence_score=0.3 + (i % 10) * 0.07,
                outcome=["accepted", "rejected", "expired", "pending"][i % 4],
                accepted_at=(base_time + timedelta(days=i)).isoformat() if i % 4 == 0 else None,
                rejected_at=(base_time + timedelta(days=i)).isoformat() if i % 4 == 1 else None,
                expired_at=(base_time + timedelta(days=i)).isoformat() if i % 4 == 2 else None,
                feedback=f"Feedback {i}" if i % 4 == 1 else None,
            )
            store.add_usage_entry(entry)

        history = store.build_usage_history()

        assert history.total_proposals == 20
        assert history.total_accepted == 5  # Every 4th starting from 0
        assert history.total_rejected == 5  # Every 4th starting from 1
        assert history.total_expired == 5  # Every 4th starting from 2
        assert history.total_pending == 5  # Every 4th starting from 3
        assert history.acceptance_rate == 0.25
        assert history.avg_confidence_score is not None
        assert 0.3 <= history.avg_confidence_score <= 1.0

    def test_build_usage_history_with_zone_filter(self, store):
        """Test usage history with zone filter."""
        # Add entries for different zones
        for zone_idx in range(3):
            for i in range(5):
                entry = PredictiveUsageEntryV1(
                    proposal_id=f"prop-zone{zone_idx}-{i}",
                    pattern_id="pattern-01",
                    zone_id=f"zone-{zone_idx:02d}",
                    module_id="light",
                    prediction_type="time_based",
                    confidence_score=0.7,
                    outcome="accepted",
                    accepted_at=datetime.now(timezone.utc).isoformat(),
                    rejected_at=None,
                    expired_at=None,
                    feedback=None,
                )
                store.add_usage_entry(entry)

        # Filter by zone
        history = store.build_usage_history(zone_id="zone-01")
        assert history.total_proposals == 5
        for entry in history.entries:
            assert entry.zone_id == "zone-01"

    def test_build_usage_history_with_type_filter(self, store):
        """Test usage history with prediction type filter."""
        # Add entries with different prediction types
        for type_idx, ptype in enumerate(["time_based", "presence_based", "calendar_based"]):
            for i in range(3):
                entry = PredictiveUsageEntryV1(
                    proposal_id=f"prop-{ptype}-{i}",
                    pattern_id="pattern-01",
                    zone_id="zone_living",
                    module_id="light",
                    prediction_type=ptype,
                    confidence_score=0.7,
                    outcome="accepted",
                    accepted_at=datetime.now(timezone.utc).isoformat(),
                    rejected_at=None,
                    expired_at=None,
                    feedback=None,
                )
                store.add_usage_entry(entry)

        # Filter by type
        history = store.build_usage_history(prediction_type="time_based")
        assert history.total_proposals == 3
        for entry in history.entries:
            assert entry.prediction_type == "time_based"

    def test_update_zone_pattern(self, store):
        """Test updating zone pattern."""
        pattern = PredictiveZonePatternEntryV1(
            zone_id="zone_living",
            zone_name="Living Room",
            total_proposals=10,
            accepted_count=6,
            rejected_count=3,
            expired_count=1,
            acceptance_rate=0.6,
            avg_confidence_score=0.75,
            most_common_prediction_type="time_based",
            last_proposal_at=datetime.now(timezone.utc).isoformat(),
            proposals_last_7_days=3,
            proposals_last_30_days=10,
            dominant_pattern_ids=["pattern-01", "pattern-02"],
        )

        store.update_zone_pattern(pattern)

        # Verify by reading back
        patterns = store.build_zone_patterns(zone_id="zone_living")
        assert len(patterns.patterns) == 1
        assert patterns.patterns[0].zone_id == "zone_living"
        assert patterns.patterns[0].total_proposals == 10
        assert patterns.patterns[0].acceptance_rate == 0.6

    def test_build_zone_patterns(self, store):
        """Test building zone patterns."""
        # Add patterns for multiple zones
        for zone_idx in range(4):
            pattern = PredictiveZonePatternEntryV1(
                zone_id=f"zone-{zone_idx:02d}",
                zone_name=f"Zone {zone_idx}",
                total_proposals=5 + zone_idx,
                accepted_count=3 + zone_idx,
                rejected_count=1,
                expired_count=1,
                acceptance_rate=0.6,
                avg_confidence_score=0.7,
                most_common_prediction_type="time_based",
                last_proposal_at=datetime.now(timezone.utc).isoformat(),
                proposals_last_7_days=3,
                proposals_last_30_days=5 + zone_idx,
                dominant_pattern_ids=["pattern-01"],
            )
            store.update_zone_pattern(pattern)

        patterns = store.build_zone_patterns()

        assert patterns.total_zones == 4
        assert patterns.zones_with_proposals == 4
        assert len(patterns.patterns) == 4

    def test_get_effectiveness_metrics_initial(self, store):
        """Test getting initial effectiveness metrics."""
        metrics = store.get_effectiveness_metrics()

        # Should return default metrics
        assert metrics.total_proposals_analyzed == 0
        assert metrics.effectiveness_score == 0.0
        assert metrics.revision == 0

    def test_update_effectiveness_metrics(self, store):
        """Test updating effectiveness metrics."""
        # Get initial metrics
        metrics = store.get_effectiveness_metrics()
        initial_revision = metrics.revision

        # Create new metrics with updated values
        updated_metrics = PredictiveEffectivenessMetricsV1(
            total_proposals_analyzed=50,
            high_confidence_proposals=20,
            high_confidence_acceptance_rate=0.85,
            low_confidence_proposals=10,
            low_confidence_acceptance_rate=0.4,
            avg_time_to_accept_minutes=metrics.avg_time_to_accept_minutes,
            avg_time_to_reject_minutes=metrics.avg_time_to_reject_minutes,
            pattern_reinforcement_count=metrics.pattern_reinforcement_count,
            pattern_degradation_count=metrics.pattern_degradation_count,
            seasonal_adaptation_events=metrics.seasonal_adaptation_events,
            effectiveness_score=0.78,
            revision=initial_revision,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )
        store.update_effectiveness_metrics(updated_metrics)

        # Verify update
        updated = store.get_effectiveness_metrics()
        assert updated.total_proposals_analyzed == 50
        assert updated.high_confidence_proposals == 20
        assert updated.high_confidence_acceptance_rate == 0.85
        assert updated.effectiveness_score == 0.78
        assert updated.revision == initial_revision + 1

    def test_add_trend_entry(self, store):
        """Test adding trend entry."""
        entry = PredictiveTrendEntryV1(
            period="daily",
            timestamp=datetime.now(timezone.utc).isoformat(),
            proposals_count=10,
            accepted_count=6,
            rejected_count=2,
            avg_confidence=0.75,
            acceptance_rate=0.6,
        )

        store.add_trend_entry(entry)

        # Verify by reading back
        trends = store.build_trends(period="daily")
        assert len(trends.trends) == 1
        assert trends.trends[0].proposals_count == 10
        assert trends.trends[0].acceptance_rate == 0.6

    def test_build_trends(self, store):
        """Test building trends."""
        # Add multiple trend entries
        for days_ago in range(10):
            entry = PredictiveTrendEntryV1(
                period="daily",
                timestamp=(datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(),
                proposals_count=5 + days_ago,
                accepted_count=2 + days_ago,
                rejected_count=1 + (days_ago % 2),
                avg_confidence=0.5 + (days_ago * 0.03),
                acceptance_rate=0.4 + (days_ago * 0.02),
            )
            store.add_trend_entry(entry)

        trends = store.build_trends(period="daily", limit=30)

        assert trends.period == "daily"
        assert trends.total_periods == 10
        assert len(trends.trends) == 10
        assert trends.trend_direction in ["improving", "declining", "stable"]

    def test_build_trends_with_limit(self, store):
        """Test building trends with limit."""
        # Add 20 trend entries
        for days_ago in range(20):
            entry = PredictiveTrendEntryV1(
                period="daily",
                timestamp=(datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(),
                proposals_count=5 + days_ago,
                accepted_count=2 + days_ago,
                rejected_count=1,
                avg_confidence=0.6,
                acceptance_rate=0.5,
            )
            store.add_trend_entry(entry)

        trends = store.build_trends(period="daily", limit=10)

        assert len(trends.trends) == 10
        assert trends.total_periods == 10

    def test_get_summary(self, store):
        """Test getting analytics summary."""
        # Add some data
        for i in range(10):
            entry = PredictiveUsageEntryV1(
                proposal_id=f"prop-{i}",
                pattern_id="pattern-01",
                zone_id=f"zone-{i % 3:02d}",
                module_id="light",
                prediction_type="time_based",
                confidence_score=0.7,
                outcome="accepted" if i < 6 else "rejected",
                accepted_at=datetime.now(timezone.utc).isoformat() if i < 6 else None,
                rejected_at=datetime.now(timezone.utc).isoformat() if i >= 6 else None,
                expired_at=None,
                feedback=None,
            )
            store.add_usage_entry(entry)

        # Update zone pattern
        pattern = PredictiveZonePatternEntryV1(
            zone_id="zone-00",
            zone_name="Zone 0",
            total_proposals=5,
            accepted_count=3,
            rejected_count=2,
            expired_count=0,
            acceptance_rate=0.6,
            avg_confidence_score=0.7,
            most_common_prediction_type="time_based",
            last_proposal_at=datetime.now(timezone.utc).isoformat(),
            proposals_last_7_days=5,
            proposals_last_30_days=5,
            dominant_pattern_ids=["pattern-01"],
        )
        store.update_zone_pattern(pattern)

        # Update effectiveness metrics
        metrics = store.get_effectiveness_metrics()
        updated_metrics = PredictiveEffectivenessMetricsV1(
            total_proposals_analyzed=10,
            high_confidence_proposals=metrics.high_confidence_proposals,
            high_confidence_acceptance_rate=metrics.high_confidence_acceptance_rate,
            low_confidence_proposals=metrics.low_confidence_proposals,
            low_confidence_acceptance_rate=metrics.low_confidence_acceptance_rate,
            avg_time_to_accept_minutes=metrics.avg_time_to_accept_minutes,
            avg_time_to_reject_minutes=metrics.avg_time_to_reject_minutes,
            pattern_reinforcement_count=metrics.pattern_reinforcement_count,
            pattern_degradation_count=metrics.pattern_degradation_count,
            seasonal_adaptation_events=metrics.seasonal_adaptation_events,
            effectiveness_score=0.72,
            revision=metrics.revision,
            latest_change_at=metrics.latest_change_at,
        )
        store.update_effectiveness_metrics(updated_metrics)

        summary = store.get_summary()

        assert summary.usage.total_proposals == 10
        assert summary.effectiveness.effectiveness_score == 0.72
        assert summary.summary_revision >= 1


class TestPredictiveAnalyticsIntegration:
    """Integration tests for Predictive Analytics."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for tests."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_predictive_analytics.db")
        yield db_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_analytics_workflow(self, temp_db):
        """Test complete analytics workflow."""
        store = PredictiveAnalyticsStore(db_path=temp_db)

        # Add multiple usage entries
        for i in range(10):
            entry = PredictiveUsageEntryV1(
                proposal_id=f"workflow-prop-{i:03d}",
                pattern_id=f"workflow-pattern-{i % 3:02d}",
                zone_id=f"workflow-zone-{i % 2:02d}",
                module_id=f"workflow-module-{i % 2:02d}",
                prediction_type=["time_based", "presence_based", "calendar_based"][i % 3],
                confidence_score=0.5 + (i * 0.05),
                outcome=["accepted", "rejected", "pending"][i % 3],
                accepted_at=datetime.now(timezone.utc).isoformat() if i % 3 == 0 else None,
                rejected_at=datetime.now(timezone.utc).isoformat() if i % 3 == 1 else None,
                expired_at=None,
                feedback=None,
            )
            store.add_usage_entry(entry)

        # Read usage history
        history = store.build_usage_history()
        assert history.total_proposals == 10
        assert history.acceptance_rate > 0

        # Update effectiveness metrics
        metrics = store.get_effectiveness_metrics()
        updated_metrics = PredictiveEffectivenessMetricsV1(
            total_proposals_analyzed=10,
            high_confidence_proposals=metrics.high_confidence_proposals,
            high_confidence_acceptance_rate=metrics.high_confidence_acceptance_rate,
            low_confidence_proposals=metrics.low_confidence_proposals,
            low_confidence_acceptance_rate=metrics.low_confidence_acceptance_rate,
            avg_time_to_accept_minutes=metrics.avg_time_to_accept_minutes,
            avg_time_to_reject_minutes=metrics.avg_time_to_reject_minutes,
            pattern_reinforcement_count=metrics.pattern_reinforcement_count,
            pattern_degradation_count=metrics.pattern_degradation_count,
            seasonal_adaptation_events=metrics.seasonal_adaptation_events,
            effectiveness_score=0.75,
            revision=metrics.revision,
            latest_change_at=metrics.latest_change_at,
        )
        store.update_effectiveness_metrics(updated_metrics)

        # Get summary
        summary = store.get_summary()
        assert summary.usage.total_proposals == 10
        assert summary.effectiveness.effectiveness_score == 0.75

    def test_zone_pattern_aggregation(self, temp_db):
        """Test zone pattern aggregation from usage entries."""
        store = PredictiveAnalyticsStore(db_path=temp_db)

        # Add entries for specific zone
        for i in range(5):
            entry = PredictiveUsageEntryV1(
                proposal_id=f"zone-prop-{i:03d}",
                pattern_id="pattern-01",
                zone_id="zone-aggregation-test",
                module_id="light",
                prediction_type="time_based",
                confidence_score=0.7,
                outcome="accepted" if i < 3 else "rejected",
                accepted_at=datetime.now(timezone.utc).isoformat() if i < 3 else None,
                rejected_at=datetime.now(timezone.utc).isoformat() if i >= 3 else None,
                expired_at=None,
                feedback=None,
            )
            store.add_usage_entry(entry)

        # Update zone pattern manually (simulating aggregation job)
        pattern = PredictiveZonePatternEntryV1(
            zone_id="zone-aggregation-test",
            zone_name="Aggregation Test Zone",
            total_proposals=5,
            accepted_count=3,
            rejected_count=2,
            expired_count=0,
            acceptance_rate=0.6,
            avg_confidence_score=0.7,
            most_common_prediction_type="time_based",
            last_proposal_at=datetime.now(timezone.utc).isoformat(),
            proposals_last_7_days=5,
            proposals_last_30_days=5,
            dominant_pattern_ids=["pattern-01"],
        )
        store.update_zone_pattern(pattern)

        # Read patterns
        patterns = store.build_zone_patterns(zone_id="zone-aggregation-test")
        assert len(patterns.patterns) == 1
        assert patterns.patterns[0].acceptance_rate == 0.6
        assert patterns.patterns[0].total_proposals == 5

    def test_revision_tracking(self, temp_db):
        """Test revision tracking for delta polling."""
        store = PredictiveAnalyticsStore(db_path=temp_db)

        # Add initial entries
        for i in range(5):
            entry = PredictiveUsageEntryV1(
                proposal_id=f"rev-prop-{i}",
                pattern_id="pattern-01",
                zone_id="zone-rev-test",
                module_id="light",
                prediction_type="time_based",
                confidence_score=0.7,
                outcome="accepted",
                accepted_at=datetime.now(timezone.utc).isoformat(),
                rejected_at=None,
                expired_at=None,
                feedback=None,
            )
            store.add_usage_entry(entry)

        # Get initial history
        history1 = store.build_usage_history()
        initial_revision = history1.revision

        # Add more entries
        for i in range(5, 10):
            entry = PredictiveUsageEntryV1(
                proposal_id=f"rev-prop-{i}",
                pattern_id="pattern-01",
                zone_id="zone-rev-test",
                module_id="light",
                prediction_type="time_based",
                confidence_score=0.75,
                outcome="accepted",
                accepted_at=datetime.now(timezone.utc).isoformat(),
                rejected_at=None,
                expired_at=None,
                feedback=None,
            )
            store.add_usage_entry(entry)

        # Get updated history
        history2 = store.build_usage_history()
        assert history2.revision > initial_revision
        assert history2.total_proposals == 10
