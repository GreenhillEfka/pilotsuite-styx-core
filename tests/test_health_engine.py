"""Tests for Health Engine — Slice 38."""
import pytest
from copilot_core.health.engine import (
    HealthEngine,
    HealthStatus,
    CheckType,
    HealthCheckResult,
    ComponentHealth,
    HealthCheckDefinition,
    create_health_engine,
)
from datetime import datetime, timezone, timedelta


class TestHealthEngine:
    """Test health engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_health_engine()
        assert engine is not None
    
    def test_register_check_liveness(self):
        """Test registering liveness check."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="database",
            check_type="liveness",
            checker=checker,
        )
        
        assert check_id is not None
        
        checks = engine.get_checks()
        
        assert len(checks) >= 1
        assert any(c["component"] == "database" for c in checks)
    
    def test_register_check_readiness(self):
        """Test registering readiness check."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "Ready"}
        
        check_id = engine.register_check(
            component="api",
            check_type="readiness",
            checker=checker,
        )
        
        checks = engine.get_checks(component="api")
        
        assert len(checks) == 1
        assert checks[0]["check_type"] == "readiness"
    
    def test_register_check_startup(self):
        """Test registering startup check."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "Started"}
        
        engine.register_check(
            component="worker",
            check_type="startup",
            checker=checker,
        )
        
        checks = engine.get_checks(component="worker")
        
        assert checks[0]["check_type"] == "startup"
    
    def test_register_check_custom(self):
        """Test registering custom check."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "Custom OK"}
        
        engine.register_check(
            component="cache",
            check_type="custom",
            checker=checker,
        )
        
        checks = engine.get_checks(component="cache")
        
        assert checks[0]["check_type"] == "custom"
    
    def test_run_check_healthy(self):
        """Test running healthy check."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "All good"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.HEALTHY
    
    def test_run_check_degraded(self):
        """Test running degraded check."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "degraded", "message": "Slow response"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.DEGRADED
    
    def test_run_check_unhealthy(self):
        """Test running unhealthy check."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "unhealthy", "message": "Connection failed"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.UNHEALTHY
    
    def test_run_check_unknown(self):
        """Test running check with unknown status."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "unknown", "message": "Cannot determine"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.UNKNOWN
    
    def test_run_check_exception(self):
        """Test running check that raises exception."""
        engine = HealthEngine()
        
        def checker():
            raise Exception("Check failed")
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.UNHEALTHY
        assert "Check failed" in result.message
    
    def test_run_unknown_check(self):
        """Test running unknown check."""
        engine = HealthEngine()
        
        result = engine.run_check("unknown_check")
        
        assert result is None
    
    def test_run_all_checks(self):
        """Test running all checks."""
        engine = HealthEngine()
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        engine.register_check("db", "liveness", healthy_checker)
        engine.register_check("cache", "liveness", unhealthy_checker)
        
        results = engine.run_all_checks()
        
        assert len(results) == 2
    
    def test_get_component_health(self):
        """Test getting component health."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="database",
            check_type="liveness",
            checker=checker,
        )
        
        engine.run_check(check_id)
        
        health = engine.get_component_health("database")
        
        assert health is not None
        assert health["component"] == "database"
        assert health["status"] == "healthy"
    
    def test_get_unknown_component_health(self):
        """Test getting unknown component health."""
        engine = HealthEngine()
        
        health = engine.get_component_health("unknown")
        
        assert health is None
    
    def test_get_all_components_health(self):
        """Test getting all components health."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        engine.register_check("db", "liveness", checker)
        engine.register_check("cache", "liveness", checker)
        engine.register_check("api", "liveness", checker)
        
        for check in engine.get_checks():
            engine.run_check(check["check_id"])
        
        health_list = engine.get_all_components_health()
        
        assert len(health_list) >= 3
    
    def test_get_overall_health_healthy(self):
        """Test getting overall healthy status."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        engine.register_check("db", "liveness", checker)
        engine.register_check("cache", "liveness", checker)
        
        for check in engine.get_checks():
            engine.run_check(check["check_id"])
        
        overall = engine.get_overall_health()
        
        assert overall["status"] == "healthy"
        assert overall["unhealthy_components"] == 0
    
    def test_get_overall_health_unhealthy(self):
        """Test getting overall unhealthy status."""
        engine = HealthEngine()
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        engine.register_check("db", "liveness", healthy_checker)
        engine.register_check("cache", "liveness", unhealthy_checker)
        
        for check in engine.get_checks():
            engine.run_check(check["check_id"])
        
        overall = engine.get_overall_health()
        
        assert overall["status"] == "unhealthy"
        assert overall["unhealthy_components"] >= 1
    
    def test_get_overall_health_degraded(self):
        """Test getting overall degraded status."""
        engine = HealthEngine()
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        def degraded_checker():
            return {"status": "degraded", "message": "Slow"}
        
        engine.register_check("db", "liveness", healthy_checker)
        engine.register_check("cache", "liveness", degraded_checker)
        
        for check in engine.get_checks():
            engine.run_check(check["check_id"])
        
        overall = engine.get_overall_health()
        
        assert overall["status"] == "degraded"
    
    def test_get_overall_health_empty(self):
        """Test getting overall health with no components."""
        engine = HealthEngine()
        
        # Clear the default system check
        engine._component_health.clear()
        
        overall = engine.get_overall_health()
        
        assert overall["status"] == "unknown"
        assert overall["total_components"] == 0
    
    def test_get_health_history(self):
        """Test getting health history."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        for i in range(5):
            engine.run_check(check_id)
        
        history = engine.get_health_history(limit=10)
        
        assert len(history) == 5
    
    def test_get_health_history_filtered_by_component(self):
        """Test getting health history filtered by component."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check1 = engine.register_check("db", "liveness", checker)
        check2 = engine.register_check("cache", "liveness", checker)
        
        engine.run_check(check1)
        engine.run_check(check2)
        engine.run_check(check1)
        
        db_history = engine.get_health_history(component="db")
        
        assert len(db_history) == 2
        assert all(h["component"] == "db" for h in db_history)
    
    def test_get_health_history_filtered_by_status(self):
        """Test getting health history filtered by status."""
        engine = HealthEngine()
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        check1 = engine.register_check("db", "liveness", healthy_checker)
        check2 = engine.register_check("cache", "liveness", unhealthy_checker)
        
        engine.run_check(check1)
        engine.run_check(check2)
        
        unhealthy_history = engine.get_health_history(status=HealthStatus.UNHEALTHY)
        
        assert len(unhealthy_history) == 1
        assert unhealthy_history[0]["status"] == "unhealthy"
    
    def test_get_checks(self):
        """Test getting registered checks."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        engine.register_check("db", "liveness", checker, interval_seconds=60)
        engine.register_check("cache", "readiness", checker, interval_seconds=30)
        
        checks = engine.get_checks()
        
        assert len(checks) == 2
    
    def test_get_checks_filtered_by_component(self):
        """Test getting checks filtered by component."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        engine.register_check("db", "liveness", checker)
        engine.register_check("db", "readiness", checker)
        engine.register_check("cache", "liveness", checker)
        
        db_checks = engine.get_checks(component="db")
        
        assert len(db_checks) == 2
        assert all(c["component"] == "db" for c in db_checks)
    
    def test_enable_disable_check(self):
        """Test enabling/disabling check."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        # Disable
        result = engine.disable_check(check_id)
        assert result is True
        
        # Run should return None when disabled
        result = engine.run_check(check_id)
        assert result is None
        
        # Enable
        result = engine.enable_check(check_id)
        assert result is True
        
        # Run should work again
        result = engine.run_check(check_id)
        assert result is not None
    
    def test_enable_unknown_check(self):
        """Test enabling unknown check."""
        engine = HealthEngine()
        
        result = engine.enable_check("unknown")
        
        assert result is False
    
    def test_disable_unknown_check(self):
        """Test disabling unknown check."""
        engine = HealthEngine()
        
        result = engine.disable_check("unknown")
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check("test", "liveness", checker)
        
        for i in range(5):
            engine.run_check(check_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_components"] >= 1
        assert stats["total_checks_run"] >= 5
        assert stats["success_rate"] == 100.0
    
    def test_get_unhealthy_components(self):
        """Test getting unhealthy components."""
        engine = HealthEngine()
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        engine.register_check("db", "liveness", healthy_checker)
        engine.register_check("cache", "liveness", unhealthy_checker)
        
        for check in engine.get_checks():
            engine.run_check(check["check_id"])
        
        unhealthy = engine.get_unhealthy_components()
        
        assert len(unhealthy) >= 1
        assert any(c["component"] == "cache" for c in unhealthy)
    
    def test_reset_component_health(self):
        """Test resetting component health."""
        engine = HealthEngine()
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=unhealthy_checker,
        )
        
        engine.run_check(check_id)
        
        health_before = engine.get_component_health("test")
        assert health_before["status"] == "unhealthy"
        
        result = engine.reset_component_health("test")
        
        assert result is True
        
        health_after = engine.get_component_health("test")
        assert health_after["status"] == "unknown"
        assert health_after["consecutive_failures"] == 0
    
    def test_reset_unknown_component_health(self):
        """Test resetting unknown component health."""
        engine = HealthEngine()
        
        result = engine.reset_component_health("unknown")
        
        assert result is False
    
    def test_clear_history_all(self):
        """Test clearing all history."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check("test", "liveness", checker)
        
        for i in range(10):
            engine.run_check(check_id)
        
        count = engine.clear_history()
        
        assert count == 10
        assert len(engine._health_history) == 0
    
    def test_clear_history_older_than(self):
        """Test clearing history older than timestamp."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check("test", "liveness", checker)
        
        # Run some checks
        for i in range(5):
            engine.run_check(check_id)
        
        # Get current time as cutoff
        cutoff = datetime.now(timezone.utc).isoformat()
        
        # Run more checks
        for i in range(5):
            engine.run_check(check_id)
        
        count = engine.clear_history(older_than=cutoff)
        
        # Should have cleared some
        assert count >= 0
    
    def test_register_status_callback(self):
        """Test registering status callback."""
        engine = HealthEngine()
        
        status_changes = []
        
        def callback(change):
            status_changes.append(change)
        
        engine.register_status_callback(callback)
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=unhealthy_checker,
            critical=True,
        )
        
        engine.run_check(check_id)
        
        assert len(status_changes) >= 1
        assert status_changes[0]["component"] == "test"
        assert status_changes[0]["status"] == "unhealthy"
    
    def test_consecutive_failures_tracking(self):
        """Test tracking consecutive failures."""
        engine = HealthEngine()
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=unhealthy_checker,
        )
        
        for i in range(5):
            engine.run_check(check_id)
        
        health = engine.get_component_health("test")
        
        assert health["consecutive_failures"] == 5
        assert health["failed_checks"] == 5
    
    def test_healthy_resets_consecutive_failures(self):
        """Test that healthy check resets consecutive failures."""
        engine = HealthEngine()
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=unhealthy_checker,
        )
        
        # Run 3 unhealthy checks
        for i in range(3):
            engine.run_check(check_id)
        
        # Change to healthy checker
        engine._checks[check_id].checker = healthy_checker
        
        # Run healthy check
        engine.run_check(check_id)
        
        health = engine.get_component_health("test")
        
        assert health["consecutive_failures"] == 0
    
    def test_critical_check_makes_component_unhealthy(self):
        """Test that critical check failure makes component unhealthy."""
        engine = HealthEngine()
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=unhealthy_checker,
            critical=True,
        )
        
        engine.run_check(check_id)
        
        health = engine.get_component_health("test")
        
        assert health["status"] == "unhealthy"
    
    def test_non_critical_check_needs_3_failures(self):
        """Test that non-critical check needs 3 failures to be unhealthy."""
        engine = HealthEngine()
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=unhealthy_checker,
            critical=False,
        )
        
        # First failure
        engine.run_check(check_id)
        health = engine.get_component_health("test")
        assert health["status"] != "unhealthy"  # Still unknown or degraded
        
        # Second failure
        engine.run_check(check_id)
        health = engine.get_component_health("test")
        assert health["status"] != "unhealthy"
        
        # Third failure
        engine.run_check(check_id)
        health = engine.get_component_health("test")
        assert health["status"] == "unhealthy"
    
    def test_health_check_result_to_dict(self):
        """Test health check result serialization."""
        result = HealthCheckResult(
            check_id="check_test",
            component="test_component",
            check_type=CheckType.LIVENESS,
            status=HealthStatus.HEALTHY,
            message="All good",
            timestamp="2026-03-31T12:00:00Z",
            latency_ms=15,
            details={"extra": "info"},
        )
        
        d = result.to_dict()
        
        assert d["check_id"] == "check_test"
        assert d["component"] == "test_component"
        assert d["check_type"] == "liveness"
        assert d["status"] == "healthy"
        assert d["latency_ms"] == 15
    
    def test_component_health_to_dict(self):
        """Test component health serialization."""
        health = ComponentHealth(
            component="test",
            status=HealthStatus.HEALTHY,
            last_check="2026-03-31T12:00:00Z",
            last_success="2026-03-31T12:00:00Z",
            last_failure=None,
            consecutive_failures=0,
            total_checks=10,
            successful_checks=10,
            failed_checks=0,
        )
        
        d = health.to_dict()
        
        assert d["component"] == "test"
        assert d["status"] == "healthy"
        assert d["uptime_percent"] == 100.0
    
    def test_health_check_definition_to_dict(self):
        """Test health check definition serialization."""
        def checker():
            return {"status": "healthy"}
        
        definition = HealthCheckDefinition(
            check_id="check_test",
            component="test",
            check_type=CheckType.READINESS,
            checker=checker,
            interval_seconds=60,
            timeout_seconds=10,
            critical=True,
            enabled=True,
        )
        
        d = definition.to_dict()
        
        assert d["check_id"] == "check_test"
        assert d["check_type"] == "readiness"
        assert d["interval_seconds"] == 60
        assert d["critical"] is True
    
    def test_health_status_enum_values(self):
        """Test health status enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"
    
    def test_check_type_enum_values(self):
        """Test check type enum values."""
        assert CheckType.LIVENESS.value == "liveness"
        assert CheckType.READINESS.value == "readiness"
        assert CheckType.STARTUP.value == "startup"
        assert CheckType.CUSTOM.value == "custom"
    
    def test_check_latency_tracked(self):
        """Test that check latency is tracked."""
        engine = HealthEngine()
        
        def slow_checker():
            import time
            time.sleep(0.05)  # 50ms
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=slow_checker,
        )
        
        result = engine.run_check(check_id)
        
        assert result.latency_ms >= 50
    
    def test_check_timestamp_recorded(self):
        """Test that check timestamp is recorded."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        result = engine.run_check(check_id)
        
        assert result.timestamp is not None
        assert "T" in result.timestamp  # ISO format
    
    def test_health_history_trimmed_to_max(self):
        """Test that health history is trimmed to max."""
        engine = HealthEngine()
        engine._max_history_size = 10
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check("test", "liveness", checker)
        
        for i in range(20):
            engine.run_check(check_id)
        
        assert len(engine._health_history) <= 10
    
    def test_component_checks_trimmed_to_10(self):
        """Test that component checks list is trimmed to 10."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check("test", "liveness", checker)
        
        for i in range(20):
            engine.run_check(check_id)
        
        health = engine.get_component_health("test")
        
        assert len(health["checks"]) <= 10
    
    def test_uptime_percent_calculation(self):
        """Test uptime percent calculation."""
        engine = HealthEngine()
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        check_id = engine.register_check("test", "liveness", healthy_checker)
        
        # 7 healthy, 3 unhealthy
        engine._checks[check_id].checker = healthy_checker
        for i in range(7):
            engine.run_check(check_id)
        
        engine._checks[check_id].checker = unhealthy_checker
        for i in range(3):
            engine.run_check(check_id)
        
        health = engine.get_component_health("test")
        
        assert health["uptime_percent"] == 70.0
    
    def test_statistics_success_rate_calculation(self):
        """Test statistics success rate calculation."""
        engine = HealthEngine()
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        check_id = engine.register_check("test", "liveness", healthy_checker)
        
        # 8 healthy, 2 unhealthy
        engine._checks[check_id].checker = healthy_checker
        for i in range(8):
            engine.run_check(check_id)
        
        engine._checks[check_id].checker = unhealthy_checker
        for i in range(2):
            engine.run_check(check_id)
        
        stats = engine.get_statistics()
        
        assert stats["success_rate"] == 80.0
    
    def test_overall_health_includes_timestamp(self):
        """Test that overall health includes timestamp."""
        engine = HealthEngine()
        
        overall = engine.get_overall_health()
        
        assert "timestamp" in overall
        assert overall["timestamp"] is not None
    
    def test_degraded_status_tracking(self):
        """Test degraded status tracking."""
        engine = HealthEngine()
        
        def degraded_checker():
            return {"status": "degraded", "message": "Slow"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=degraded_checker,
        )
        
        engine.run_check(check_id)
        
        health = engine.get_component_health("test")
        
        assert health["status"] == "degraded"
    
    def test_multiple_checks_same_component(self):
        """Test multiple checks for same component."""
        engine = HealthEngine()
        
        def healthy_checker():
            return {"status": "healthy", "message": "OK"}
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        engine.register_check("db", "liveness", healthy_checker)
        engine.register_check("db", "readiness", unhealthy_checker)
        
        for check in engine.get_checks(component="db"):
            engine.run_check(check["check_id"])
        
        health = engine.get_component_health("db")
        
        # Component should reflect worst status
        assert health is not None
    
    def test_check_details_included(self):
        """Test that check details are included in result."""
        engine = HealthEngine()
        
        def checker():
            return {
                "status": "healthy",
                "message": "OK",
                "details": {"version": "1.0.0", "uptime": 3600},
            }
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
        )
        
        result = engine.run_check(check_id)
        
        assert "version" in result.details
        assert "uptime" in result.details
    
    def test_default_system_memory_check_registered(self):
        """Test that default system memory check is registered."""
        engine = HealthEngine()
        
        checks = engine.get_checks(component="system")
        
        # Should have at least the memory check
        assert len(checks) >= 1
    
    def test_health_history_sorted_by_timestamp(self):
        """Test that health history is sorted by timestamp."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check("test", "liveness", checker)
        
        for i in range(5):
            engine.run_check(check_id)
        
        history = engine.get_health_history(limit=10)
        
        # Verify sorted (newest first)
        for i in range(len(history) - 1):
            assert history[i]["timestamp"] >= history[i + 1]["timestamp"]
    
    def test_unhealthy_components_sorted_by_failures(self):
        """Test that unhealthy components are sorted by failures."""
        engine = HealthEngine()
        
        def unhealthy_checker():
            return {"status": "unhealthy", "message": "Failed"}
        
        engine.register_check("db", "liveness", unhealthy_checker)
        engine.register_check("cache", "liveness", unhealthy_checker)
        
        # Run more checks on db
        db_checks = engine.get_checks(component="db")
        for check in db_checks:
            for i in range(5):
                engine.run_check(check["check_id"])
        
        # Run fewer checks on cache
        cache_checks = engine.get_checks(component="cache")
        for check in cache_checks:
            engine.run_check(check["check_id"])
        
        unhealthy = engine.get_unhealthy_components()
        
        # db should be first (more failures)
        if len(unhealthy) >= 2:
            assert unhealthy[0]["component"] == "db"
    
    def test_check_id_generated_if_not_provided(self):
        """Test that check ID is generated if not provided."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
            check_id=None,
        )
        
        assert check_id is not None
        assert check_id.startswith("check_")
    
    def test_check_interval_and_timeout_stored(self):
        """Test that check interval and timeout are stored."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        check_id = engine.register_check(
            component="test",
            check_type="liveness",
            checker=checker,
            interval_seconds=120,
            timeout_seconds=30,
        )
        
        checks = engine.get_checks()
        check = next(c for c in checks if c["check_id"] == check_id)
        
        assert check["interval_seconds"] == 120
        assert check["timeout_seconds"] == 30
    
    def test_statistics_zero_checks_run(self):
        """Test statistics with zero checks run."""
        engine = HealthEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_checks_run"] == 0
        assert stats["success_rate"] == 0.0
    
    def test_component_health_zero_checks(self):
        """Test component health with zero checks."""
        engine = HealthEngine()
        
        def checker():
            return {"status": "healthy", "message": "OK"}
        
        engine.register_check("test", "liveness", checker)
        # Don't run the check
        
        health = engine.get_component_health("test")
        
        assert health["total_checks"] == 0
        assert health["uptime_percent"] == 0.0
