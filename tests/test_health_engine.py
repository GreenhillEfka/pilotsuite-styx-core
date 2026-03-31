"""Tests for Health Check & System Monitoring — Slice 24."""
import pytest
from copilot_core.health.engine import (
    HealthCheckEngine,
    HealthStatus,
    ComponentType,
    create_health_check_engine,
)


class TestHealthCheckEngine:
    """Test health check engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_health_check_engine()
        assert engine is not None
    
    def test_register_component(self):
        """Test component registration."""
        engine = HealthCheckEngine()
        
        comp_id = engine.register_component(
            component_id="cpu_main",
            component_type=ComponentType.CPU,
            name="Main CPU",
            initial_value=0.0,
        )
        
        assert comp_id == "cpu_main"
        assert comp_id in engine._components
        assert engine._components[comp_id].name == "Main CPU"
    
    def test_update_component_healthy(self):
        """Test updating component - healthy state."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        component = engine.update_component_value("cpu_test", 45.0)
        
        assert component.status == HealthStatus.HEALTHY
        assert component.value == 45.0
    
    def test_update_component_warning(self):
        """Test updating component - warning state."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        component = engine.update_component_value("cpu_test", 85.0)
        
        assert component.status == HealthStatus.WARNING
        assert "Warning" in component.message
    
    def test_update_component_critical(self):
        """Test updating component - critical state."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        component = engine.update_component_value("cpu_test", 98.0)
        
        assert component.status == HealthStatus.CRITICAL
        assert "Critical" in component.message
    
    def test_update_unknown_component(self):
        """Test updating unknown component."""
        engine = HealthCheckEngine()
        
        with pytest.raises(ValueError):
            engine.update_component_value("unknown_component", 50.0)
    
    def test_get_system_health_empty(self):
        """Test system health with no components."""
        engine = HealthCheckEngine()
        
        health = engine.get_system_health()
        
        assert health.overall_status == HealthStatus.UNKNOWN
        assert health.health_score == 0.0
        assert len(health.components) == 0
    
    def test_get_system_health_healthy(self):
        """Test system health - all healthy."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        engine.update_component_value("cpu_test", 30.0)
        
        health = engine.get_system_health()
        
        assert health.overall_status == HealthStatus.HEALTHY
        assert health.health_score == 100.0
    
    def test_get_system_health_degraded(self):
        """Test system health - degraded."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        engine.update_component_value("cpu_test", 85.0)  # Warning
        
        health = engine.get_system_health()
        
        assert health.overall_status == HealthStatus.WARNING
        assert len(health.warnings) >= 1
    
    def test_get_system_health_critical(self):
        """Test system health - critical."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        engine.update_component_value("cpu_test", 98.0)  # Critical
        
        health = engine.get_system_health()
        
        assert health.overall_status == HealthStatus.CRITICAL
        assert len(health.critical_issues) >= 1
    
    def test_get_component_health(self):
        """Test getting component health."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        engine.update_component_value("cpu_test", 50.0)
        
        comp = engine.get_component_health("cpu_test")
        
        assert comp is not None
        assert comp["component_id"] == "cpu_test"
        assert comp["name"] == "Test CPU"
    
    def test_get_unknown_component_health(self):
        """Test getting unknown component health."""
        engine = HealthCheckEngine()
        
        comp = engine.get_component_health("unknown_component")
        
        assert comp is None
    
    def test_get_all_components(self):
        """Test getting all components."""
        engine = HealthCheckEngine()
        
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        engine.register_component("mem_test", ComponentType.MEMORY, "Test Memory")
        
        components = engine.get_all_components()
        
        assert len(components) == 2
    
    def test_alert_creation_on_critical(self):
        """Test that alerts are created on critical status."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        engine.update_component_value("cpu_test", 98.0)
        
        alerts = engine.get_alerts(unresolved_only=True)
        
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "critical"
    
    def test_alert_creation_on_warning(self):
        """Test that alerts are created on warning status."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        engine.update_component_value("cpu_test", 85.0)
        
        alerts = engine.get_alerts(unresolved_only=True)
        
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "warning"
    
    def test_acknowledge_alert(self):
        """Test acknowledging alert."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        engine.update_component_value("cpu_test", 98.0)
        
        alerts = engine.get_alerts(unresolved_only=True)
        alert_id = alerts[0]["alert_id"]
        
        result = engine.acknowledge_alert(alert_id)
        
        assert result is True
        
        # Should not appear in unresolved
        unresolved = engine.get_alerts(unresolved_only=True)
        assert not any(a["alert_id"] == alert_id for a in unresolved)
    
    def test_acknowledge_unknown_alert(self):
        """Test acknowledging unknown alert."""
        engine = HealthCheckEngine()
        
        result = engine.acknowledge_alert("unknown_alert")
        
        assert result is False
    
    def test_get_health_trend(self):
        """Test health trend calculation."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        # Add some history by getting health multiple times
        for i in range(10):
            engine.update_component_value("cpu_test", 50.0 + i)
            engine.get_system_health()
        
        trend = engine.get_health_trend(hours=24)
        
        assert trend["data_points"] >= 1
        assert "avg_health_score" in trend
        assert "trend" in trend
    
    def test_get_health_trend_empty(self):
        """Test health trend with no history."""
        engine = HealthCheckEngine()
        
        trend = engine.get_health_trend(hours=24)
        
        assert trend["data_points"] == 0
        assert trend["avg_health_score"] == 0.0
    
    def test_get_health_summary(self):
        """Test health summary."""
        engine = HealthCheckEngine()
        
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        engine.register_component("mem_test", ComponentType.MEMORY, "Test Memory")
        
        engine.update_component_value("cpu_test", 30.0)  # Healthy
        engine.update_component_value("mem_test", 90.0)  # Warning
        
        summary = engine.get_health_summary()
        
        assert summary["total_components"] == 2
        assert summary["healthy_components"] == 1
        assert summary["warning_components"] == 1
        assert summary["critical_components"] == 0
    
    def test_set_custom_thresholds(self):
        """Test setting custom thresholds."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        # Set custom thresholds (lower than default)
        result = engine.set_thresholds("cpu_test", warning=50.0, critical=70.0)
        
        assert result is True
        
        # Update value that would be healthy with default thresholds
        component = engine.update_component_value("cpu_test", 60.0)
        
        # Should now be warning due to custom threshold
        assert component.status == HealthStatus.WARNING
    
    def test_set_thresholds_unknown_component(self):
        """Test setting thresholds for unknown component."""
        engine = HealthCheckEngine()
        
        result = engine.set_thresholds("unknown_component", warning=50.0, critical=70.0)
        
        assert result is False
    
    def test_health_history_trimming(self):
        """Test that health history is trimmed to max size."""
        engine = HealthCheckEngine()
        engine._max_history_size = 10
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        # Generate more than max history entries
        for i in range(20):
            engine.update_component_value("cpu_test", float(i))
            engine.get_system_health()
        
        assert len(engine._health_history) <= 10
    
    def test_component_to_dict(self):
        """Test component serialization."""
        from copilot_core.health.engine import ComponentHealth
        
        comp = ComponentHealth(
            component_id="cpu_test",
            component_type=ComponentType.CPU,
            name="Test CPU",
            status=HealthStatus.HEALTHY,
            value=45.0,
            threshold_warning=80.0,
            threshold_critical=95.0,
            unit="%",
        )
        
        d = comp.to_dict()
        
        assert d["component_id"] == "cpu_test"
        assert d["component_type"] == "cpu"
        assert d["status"] == "healthy"
        assert d["value"] == 45.0
    
    def test_system_health_to_dict(self):
        """Test system health serialization."""
        from copilot_core.health.engine import SystemHealth, ComponentHealth
        
        health = SystemHealth(
            timestamp="2026-03-31T12:00:00Z",
            overall_status=HealthStatus.HEALTHY,
            health_score=95.0,
            components={},
            warnings=[],
            critical_issues=[],
            recommendations=[],
        )
        
        d = health.to_dict()
        
        assert d["timestamp"] == "2026-03-31T12:00:00Z"
        assert d["overall_status"] == "healthy"
        assert d["health_score"] == 95.0
    
    def test_alert_to_dict(self):
        """Test alert serialization."""
        from copilot_core.health.engine import HealthAlert
        
        alert = HealthAlert(
            alert_id="alert_test",
            component_id="cpu_test",
            severity=HealthStatus.CRITICAL,
            title="CPU Critical",
            message="CPU usage critical",
            value=98.0,
            threshold=95.0,
        )
        
        d = alert.to_dict()
        
        assert d["alert_id"] == "alert_test"
        assert d["severity"] == "critical"
        assert d["value"] == 98.0
        assert d["acknowledged"] is False
    
    def test_different_component_types(self):
        """Test different component types."""
        engine = HealthCheckEngine()
        
        # Register different component types
        engine.register_component("cpu_1", ComponentType.CPU, "CPU")
        engine.register_component("mem_1", ComponentType.MEMORY, "Memory")
        engine.register_component("disk_1", ComponentType.DISK, "Disk")
        engine.register_component("net_1", ComponentType.NETWORK, "Network")
        
        # Update with values
        engine.update_component_value("cpu_1", 50.0)
        engine.update_component_value("mem_1", 60.0)
        engine.update_component_value("disk_1", 70.0)
        engine.update_component_value("net_1", 100.0)  # ms latency
        
        # All should be healthy with default thresholds
        for comp_id in ["cpu_1", "mem_1", "disk_1", "net_1"]:
            comp = engine._components[comp_id]
            assert comp.status == HealthStatus.HEALTHY
    
    def test_alerts_sorted_newest_first(self):
        """Test that alerts are sorted newest first."""
        engine = HealthCheckEngine()
        engine.register_component("cpu_test", ComponentType.CPU, "Test CPU")
        
        # Create multiple alerts
        for i in range(5):
            engine.update_component_value("cpu_test", 98.0)  # Critical
        
        alerts = engine.get_alerts(unresolved_only=True)
        
        # Verify sorted by created_at (newest first)
        for i in range(len(alerts) - 1):
            assert alerts[i]["created_at"] >= alerts[i + 1]["created_at"]
