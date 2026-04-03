"""Unified Analytics Dashboard Contract Tests — Slice 63."""

from __future__ import annotations

from pathlib import Path

import pytest

from copilot_core.analytics.unified_analytics import (
    AnalyticsModuleSummaryV1,
    UnifiedAnalyticsDashboard,
    UnifiedAnalyticsDashboardV1,
)


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Create temporary data directory."""
    return tmp_path / "analytics_data"


@pytest.fixture
def dashboard(temp_data_dir: Path) -> UnifiedAnalyticsDashboard:
    """Create unified analytics dashboard."""
    return UnifiedAnalyticsDashboard(temp_data_dir)


class TestAnalyticsModuleSummaryV1:
    """Test AnalyticsModuleSummaryV1 dataclass."""

    def test_summary_creation(self) -> None:
        """Test basic summary creation."""
        summary = AnalyticsModuleSummaryV1(
            module="zone_truth",
            total_events=100,
            revision=50,
            last_event_at=1234567890.0,
            health_score=0.85,
            key_metrics={"sync_success_rate": 0.9},
        )

        assert summary.module == "zone_truth"
        assert summary.total_events == 100
        assert summary.health_score == 0.85

    def test_summary_to_dict(self) -> None:
        """Test summary serialization."""
        summary = AnalyticsModuleSummaryV1(
            module="proposal_lifecycle",
            total_events=50,
            revision=25,
            last_event_at=None,
            health_score=0.7,
            key_metrics={"acceptance_rate": 0.6},
        )

        d = summary.to_dict()
        assert d["module"] == "proposal_lifecycle"
        assert d["total_events"] == 50
        assert d["health_score"] == 0.7
        assert d["key_metrics"] == {"acceptance_rate": 0.6}


class TestUnifiedAnalyticsDashboardV1:
    """Test UnifiedAnalyticsDashboardV1 dataclass."""

    def test_dashboard_creation(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test dashboard creation."""
        result = dashboard.build_dashboard()

        assert isinstance(result, UnifiedAnalyticsDashboardV1)
        assert result.global_revision >= 0
        assert result.time_range_days == 30
        assert len(result.modules) == 5  # All 5 analytics modules
        assert 0.0 <= result.overall_health_score <= 1.0

    def test_dashboard_to_dict(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test dashboard serialization."""
        result = dashboard.build_dashboard()
        d = result.to_dict()

        assert "generated_at" in d
        assert "global_revision" in d
        assert "time_range_days" in d
        assert "modules" in d
        assert "overall_health_score" in d
        assert "total_events_all_modules" in d
        assert "zones_active" in d
        assert "anomalies" in d
        assert "recommendations" in d
        assert len(d["modules"]) == 5

    def test_dashboard_with_custom_days(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test dashboard with custom time range."""
        result = dashboard.build_dashboard(days_lookback=7)

        assert result.time_range_days == 7

    def test_dashboard_modules_present(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test all expected modules are present."""
        result = dashboard.build_dashboard()
        module_names = [m.module for m in result.modules]

        assert "zone_truth" in module_names
        assert "proposal_lifecycle" in module_names
        assert "action_closure" in module_names
        assert "brain_neuron" in module_names
        assert "chat_rag" in module_names


class TestUnifiedAnalyticsDashboard:
    """Test UnifiedAnalyticsDashboard operations."""

    def test_health_score_calculation(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test health score calculation."""
        # High activity, no errors, high completion = high score
        score = dashboard._calculate_health_score(
            total_events=100,
            error_rate=0.0,
            completion_rate=1.0,
        )
        assert score > 0.7

        # No activity = neutral score
        score = dashboard._calculate_health_score(
            total_events=0,
            error_rate=0.0,
            completion_rate=1.0,
        )
        assert score == 0.5

        # High errors = lower score (but activity still contributes)
        score = dashboard._calculate_health_score(
            total_events=100,
            error_rate=0.8,
            completion_rate=0.2,
        )
        assert score < 0.7  # Should be lower than the high-success case

    def test_anomaly_detection_low_health(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test anomaly detection for low health scores."""
        modules = [
            AnalyticsModuleSummaryV1(
                module="test_module",
                total_events=10,
                revision=1,
                last_event_at=None,
                health_score=0.15,  # Very low
            ),
        ]

        anomalies = dashboard._detect_anomalies(modules)

        assert len(anomalies) >= 1
        assert any(a["type"] == "low_health" for a in anomalies)

    def test_anomaly_detection_high_errors(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test anomaly detection for high error rates."""
        modules = [
            AnalyticsModuleSummaryV1(
                module="test_module",
                total_events=100,
                revision=1,
                last_event_at=None,
                health_score=0.5,
                key_metrics={"error_rate": 0.6},
            ),
        ]

        anomalies = dashboard._detect_anomalies(modules)

        assert len(anomalies) >= 1
        assert any(a["type"] == "high_error_rate" for a in anomalies)

    def test_recommendations_inactive_modules(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test recommendations for inactive modules."""
        modules = [
            AnalyticsModuleSummaryV1(
                module="inactive_module",
                total_events=0,
                revision=0,
                last_event_at=None,
                health_score=0.5,
            ),
        ]

        recommendations = dashboard._generate_recommendations(modules, [])

        assert len(recommendations) >= 1
        assert "inactive_module" in recommendations[0]

    def test_recommendations_high_errors(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test recommendations for high error rates."""
        anomalies = [
            {
                "type": "high_error_rate",
                "module": "test_module",
                "severity": "high",
                "message": "High errors",
            },
        ]

        recommendations = dashboard._generate_recommendations([], anomalies)

        assert len(recommendations) >= 1
        assert "test_module" in recommendations[0]

    def test_build_zone_summary(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test zone summary building."""
        summary = dashboard._build_zone_summary(days_lookback=30)

        assert summary.module == "zone_truth"
        assert "sync_success_rate" in summary.key_metrics
        assert "conflict_rate" in summary.key_metrics
        assert 0.0 <= summary.health_score <= 1.0

    def test_build_proposal_summary(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test proposal summary building."""
        summary = dashboard._build_proposal_summary(days_lookback=30)

        assert summary.module == "proposal_lifecycle"
        assert "acceptance_rate" in summary.key_metrics
        assert "execution_rate" in summary.key_metrics

    def test_build_closure_summary(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test closure summary building."""
        summary = dashboard._build_closure_summary(days_lookback=30)

        assert summary.module == "action_closure"
        assert "completion_rate" in summary.key_metrics
        assert "failure_rate" in summary.key_metrics

    def test_build_brain_summary(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test brain summary building."""
        summary = dashboard._build_brain_summary(days_lookback=30)

        assert summary.module == "brain_neuron"
        assert "activation_rate" in summary.key_metrics
        assert "evaluation_rate" in summary.key_metrics

    def test_build_chat_summary(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test chat summary building."""
        summary = dashboard._build_chat_summary(days_lookback=30)

        assert summary.module == "chat_rag"
        assert "response_rate" in summary.key_metrics
        assert "error_rate" in summary.key_metrics

    def test_dashboard_global_revision(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test global revision is max of all modules."""
        result = dashboard.build_dashboard()

        module_revisions = [m.revision for m in result.modules]
        assert result.global_revision == max(module_revisions)

    def test_dashboard_total_events(self, dashboard: UnifiedAnalyticsDashboard) -> None:
        """Test total events is sum of all modules."""
        result = dashboard.build_dashboard()

        module_events = sum(m.total_events for m in result.modules)
        assert result.total_events_all_modules == module_events
