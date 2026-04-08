"""Tests for Predictive Maintenance Engine (v6.1.0)."""

import pytest
from copilot_core.hub.predictive_maintenance import (
    PredictiveMaintenanceEngine,
    DeviceHealth,
    DeviceMetric,
    MaintenanceSummary,
)


class TestRegistration:
    """Tests for device registration."""

    def test_register_device(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("sensor_1", "Living Room Temp", "sensor")
        assert engine.device_count == 1

    def test_register_multiple(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        engine.register_device("a1", "Actuator 1", "actuator")
        assert engine.device_count == 2

    def test_duplicate_registration_ignored(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        engine.register_device("s1", "Sensor 1 Dup", "sensor")
        assert engine.device_count == 1


class TestMetrics:
    """Tests for metric ingestion."""

    def test_ingest_metric(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        engine.ingest_metric("s1", "battery_level", 85.0)
        device = engine.get_device("s1")
        assert device["metrics"]["battery_level"] == 85.0

    def test_ingest_unregistered_ignored(self):
        engine = PredictiveMaintenanceEngine()
        engine.ingest_metric("unknown", "battery_level", 50.0)
        assert engine.device_count == 0

    def test_ingest_batch(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        count = engine.ingest_metrics_batch([
            {"device_id": "s1", "metric": "battery_level", "value": 90},
            {"device_id": "s1", "metric": "response_time_ms", "value": 150},
            {"device_id": "s1", "metric": "signal_strength", "value": -60},
        ])
        assert count == 3
        device = engine.get_device("s1")
        assert device["metrics"]["response_time_ms"] == 150

    def test_history_limit(self):
        engine = PredictiveMaintenanceEngine()
        engine._max_history = 10
        engine.register_device("s1", "Sensor", "sensor")
        for i in range(20):
            engine.ingest_metric("s1", "battery_level", 100 - i)
        assert len(engine._history["s1"]) == 10


class TestHealthScoring:
    """Tests for health score calculation."""

    def test_healthy_device(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        engine.ingest_metric("s1", "battery_level", 90.0)
        engine.ingest_metric("s1", "response_time_ms", 100.0)
        engine.ingest_metric("s1", "signal_strength", -50.0)
        engine.ingest_metric("s1", "uptime_pct", 99.5)
        device = engine.evaluate_device("s1")
        assert device.health_score >= 80
        assert device.status == "healthy"

    def test_degraded_device(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        engine.ingest_metric("s1", "battery_level", 15.0)  # below warning
        device = engine.evaluate_device("s1")
        assert device.health_score < 80

    def test_critical_device(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        engine.ingest_metric("s1", "battery_level", 5.0)
        engine.ingest_metric("s1", "response_time_ms", 6000.0)
        engine.ingest_metric("s1", "signal_strength", -90.0)
        device = engine.evaluate_device("s1")
        assert device.health_score < 30
        assert device.status == "critical"

    def test_no_metrics_is_healthy(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        device = engine.evaluate_device("s1")
        assert device.health_score == 100.0
        assert device.status == "healthy"

    def test_actuator_weights(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("a1", "Actuator", "actuator")
        engine.ingest_metric("a1", "error_count", 25.0)
        device = engine.evaluate_device("a1")
        assert device.health_score < 80

    def test_controller_weights(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("c1", "Controller", "controller")
        engine.ingest_metric("c1", "uptime_pct", 75.0)
        device = engine.evaluate_device("c1")
        assert device.health_score < 80


class TestIssuesAndRecommendations:
    """Tests for issue identification and recommendations."""

    def test_battery_issue(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor", "sensor")
        engine.ingest_metric("s1", "battery_level", 8.0)
        device = engine.evaluate_device("s1")
        assert any("battery_level" in i for i in device.issues)

    def test_battery_recommendation(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor", "sensor")
        engine.ingest_metric("s1", "battery_level", 15.0)
        device = engine.evaluate_device("s1")
        assert any("Batterie" in r for r in device.recommendations)

    def test_error_count_recommendation(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("a1", "Actuator", "actuator")
        engine.ingest_metric("a1", "error_count", 15.0)
        device = engine.evaluate_device("a1")
        assert any("starten" in r for r in device.recommendations)

    def test_signal_recommendation(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor", "sensor")
        engine.ingest_metric("s1", "signal_strength", -82.0)
        device = engine.evaluate_device("s1")
        assert any("Gateway" in r or "Router" in r for r in device.recommendations)

    def test_no_issues_when_healthy(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor", "sensor")
        engine.ingest_metric("s1", "battery_level", 90.0)
        device = engine.evaluate_device("s1")
        assert len(device.issues) == 0


class TestDegradation:
    """Tests for degradation tracking."""

    def test_degradation_with_history(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor", "sensor")
        # Simulate battery drain over 48 readings (2 days)
        for i in range(48):
            engine.ingest_metric("s1", "battery_level", 100.0 - i * 1.0)
        device = engine.evaluate_device("s1")
        assert device.degradation_rate > 0

    def test_no_degradation_stable(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor", "sensor")
        for i in range(24):
            engine.ingest_metric("s1", "battery_level", 90.0)
        device = engine.evaluate_device("s1")
        assert device.degradation_rate == 0.0

    def test_failure_prediction(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor", "sensor")
        for i in range(48):
            engine.ingest_metric("s1", "battery_level", 50.0 - i * 0.5)
        device = engine.evaluate_device("s1")
        if device.degradation_rate > 0:
            assert device.estimated_days_to_failure >= 0


class TestSummary:
    """Tests for maintenance summary."""

    def test_empty_summary(self):
        engine = PredictiveMaintenanceEngine()
        summary = engine.get_summary()
        assert summary.ok is True
        assert summary.total_devices == 0

    def test_mixed_health(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Good Sensor", "sensor")
        engine.ingest_metric("s1", "battery_level", 90.0)
        engine.register_device("s2", "Bad Sensor", "sensor")
        engine.ingest_metric("s2", "battery_level", 5.0)
        summary = engine.get_summary()
        assert summary.total_devices == 2
        assert summary.healthy >= 1
        assert len(summary.devices_needing_attention) >= 1

    def test_avg_health_score(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Sensor 1", "sensor")
        engine.register_device("s2", "Sensor 2", "sensor")
        summary = engine.get_summary()
        assert summary.avg_health_score == 100.0  # both have no metrics

    def test_get_device_details(self):
        engine = PredictiveMaintenanceEngine()
        engine.register_device("s1", "Living Room", "sensor")
        engine.ingest_metric("s1", "battery_level", 70.0)
        info = engine.get_device("s1")
        assert info["name"] == "Living Room"
        assert info["device_type"] == "sensor"
        assert "battery_level" in info["metrics"]

    def test_get_nonexistent_device(self):
        engine = PredictiveMaintenanceEngine()
        assert engine.get_device("nonexistent") is None
