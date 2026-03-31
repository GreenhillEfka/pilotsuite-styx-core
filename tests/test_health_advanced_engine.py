"""Tests for Health Advanced Engine — Slice 60."""
import pytest
from copilot_core.health_advanced.engine import (
    HealthEngine,
    HealthStatus,
    CheckType,
    HealthCheck,
    HealthCheckResult,
    HealthAggregation,
    create_health_engine,
)
from datetime import datetime, timezone
import time


class TestHealthCheckResult:
    """Test health check result."""
    
    def test_create_result(self):
        """Test creating health check result."""
        result = HealthCheckResult(
            check_id="hc_test",
            name="Test Check",
            status=HealthStatus.HEALTHY,
            message="All good",
            response_time_ms=15.5,
        )
        
        assert result.check_id == "hc_test"
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms == 15.5
    
    def test_result_to_dict(self):
        """Test result serialization."""
        result = HealthCheckResult(
            check_id="hc_test",
            name="Test",
            status=HealthStatus.DEGRADED,
            message="Warning",
            response_time_ms=50.0,
            metadata={"cpu": 85},
        )
        
        d = result.to_dict()
        
        assert d["status"] == "degraded"
        assert d["response_time_ms"] == 50.0
        assert d["metadata"]["cpu"] == 85
    
    def test_result_timestamp_set(self):
        """Test that result timestamp is set."""
        result = HealthCheckResult(
            check_id="hc_test",
            name="Test",
            status=HealthStatus.HEALTHY,
            message="OK",
        )
        
        assert result.timestamp is not None


class TestHealthCheck:
    """Test health check definition."""
    
    def test_create_check(self):
        """Test creating health check."""
        check = HealthCheck(
            check_id="hc_test",
            name="Test Check",
            check_type=CheckType.HTTP,
            handler=None,
        )
        
        assert check.check_id == "hc_test"
        assert check.critical is True
        assert check.enabled is True
    
    def test_check_to_dict(self):
        """Test check serialization."""
        check = HealthCheck(
            check_id="hc_test",
            name="Test",
            check_type=CheckType.TCP,
            handler=None,
            timeout_seconds=5.0,
            interval_seconds=60,
            dependencies=["hc_dep1"],
        )
        
        d = check.to_dict()
        
        assert d["check_type"] == "tcp"
        assert d["timeout_seconds"] == 5.0
        assert "hc_dep1" in d["dependencies"]


class TestHealthAggregation:
    """Test health aggregation."""
    
    def test_create_aggregation(self):
        """Test creating health aggregation."""
        agg = HealthAggregation(
            overall_status=HealthStatus.DEGRADED,
            total_checks=5,
            healthy_checks=3,
            degraded_checks=1,
            unhealthy_checks=1,
            unknown_checks=0,
            critical_healthy=2,
            critical_unhealthy=0,
        )
        
        assert agg.overall_status == HealthStatus.DEGRADED
        assert agg.total_checks == 5
    
    def test_aggregation_to_dict(self):
        """Test aggregation serialization."""
        agg = HealthAggregation(
            overall_status=HealthStatus.HEALTHY,
            total_checks=3,
            healthy_checks=3,
            degraded_checks=0,
            unhealthy_checks=0,
            unknown_checks=0,
            critical_healthy=1,
            critical_unhealthy=0,
        )
        
        d = agg.to_dict()
        
        assert d["overall_status"] == "healthy"
        assert d["healthy_checks"] == 3


class TestHealthEngine:
    """Test health engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_health_engine()
        assert engine is not None
    
    def test_register_check(self):
        """Test registering health check."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check(
            name="Test Check",
            check_type=CheckType.CUSTOM,
            handler=handler,
        )
        
        assert check_id is not None
        assert check_id.startswith("hc_")
        
        check = engine._checks.get(check_id)
        
        assert check is not None
        assert check.name == "Test Check"
    
    def test_register_check_with_dependencies(self):
        """Test registering check with dependencies."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        dep_id = engine.register_check("Dependency", CheckType.CUSTOM, handler)
        
        check_id = engine.register_check(
            name="Dependent Check",
            check_type=CheckType.CUSTOM,
            handler=handler,
            dependencies=[dep_id],
        )
        
        check = engine._checks.get(check_id)
        
        assert dep_id in check.dependencies
    
    def test_register_check_with_thresholds(self):
        """Test registering check with thresholds."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check(
            name="Threshold Check",
            check_type=CheckType.MEMORY,
            handler=handler,
            thresholds={"warning": 0.8, "critical": 0.9},
        )
        
        check = engine._checks.get(check_id)
        
        assert check.thresholds["warning"] == 0.8
    
    def test_unregister_check(self):
        """Test unregistering health check."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        result = engine.unregister_check(check_id)
        
        assert result is True
        assert check_id not in engine._checks
    
    def test_unregister_nonexistent_check(self):
        """Test unregistering nonexistent check."""
        engine = HealthEngine()
        
        result = engine.unregister_check("nonexistent")
        
        assert result is False
    
    def test_run_check(self):
        """Test running health check."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult(
                check_id="",
                name="Test",
                status=HealthStatus.HEALTHY,
                message="OK",
                response_time_ms=10.0,
            )
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "OK"
    
    def test_run_check_disabled(self):
        """Test running disabled check."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        engine.disable_check(check_id)
        
        result = engine.run_check(check_id)
        
        assert result is None
    
    def test_run_check_with_timeout(self):
        """Test running check with timeout."""
        engine = HealthEngine()
        
        def slow_handler():
            time.sleep(2)
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check(
            name="Slow Check",
            check_type=CheckType.CUSTOM,
            handler=slow_handler,
            timeout_seconds=0.1,
        )
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.message
    
    def test_run_check_with_exception(self):
        """Test running check that raises exception."""
        engine = HealthEngine()
        
        def failing_handler():
            raise RuntimeError("Test error")
        
        check_id = engine.register_check("Failing", CheckType.CUSTOM, failing_handler)
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.UNHEALTHY
        assert "Test error" in result.message
    
    def test_run_check_updates_last_result(self):
        """Test that run_check updates last_result."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        engine.run_check(check_id)
        
        check = engine._checks.get(check_id)
        
        assert check.last_result is not None
        assert check.last_result.status == HealthStatus.HEALTHY
    
    def test_run_check_updates_consecutive_failures(self):
        """Test that run_check updates consecutive failures."""
        engine = HealthEngine()
        
        def failing_handler():
            raise RuntimeError("Fail")
        
        check_id = engine.register_check("Failing", CheckType.CUSTOM, failing_handler)
        
        engine.run_check(check_id)
        engine.run_check(check_id)
        engine.run_check(check_id)
        
        check = engine._checks.get(check_id)
        
        assert check.consecutive_failures == 3
    
    def test_run_check_resets_failures_on_success(self):
        """Test that success resets consecutive failures."""
        engine = HealthEngine()
        
        fail = True
        
        def handler():
            if fail:
                raise RuntimeError("Fail")
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        # Three failures
        for _ in range(3):
            engine.run_check(check_id)
        
        # Success
        fail = False
        engine.run_check(check_id)
        
        check = engine._checks.get(check_id)
        
        assert check.consecutive_failures == 0
    
    def test_get_health_all_healthy(self):
        """Test health aggregation when all healthy."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        engine.register_check("Test 1", CheckType.CUSTOM, handler)
        engine.register_check("Test 2", CheckType.CUSTOM, handler)
        
        # Run checks
        for check_id in list(engine._checks.keys()):
            engine.run_check(check_id)
        
        health = engine.get_health()
        
        assert health.overall_status == HealthStatus.HEALTHY
        assert health.healthy_checks == 2
        assert health.unhealthy_checks == 0
    
    def test_get_health_with_unhealthy(self):
        """Test health aggregation with unhealthy check."""
        engine = HealthEngine()
        
        def healthy_handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        def unhealthy_handler():
            return HealthCheckResult("", "Test", HealthStatus.UNHEALTHY, "Error")
        
        engine.register_check("Healthy", CheckType.CUSTOM, healthy_handler)
        engine.register_check("Unhealthy", CheckType.CUSTOM, unhealthy_handler)
        
        # Run checks
        for check_id in list(engine._checks.keys()):
            engine.run_check(check_id)
        
        health = engine.get_health()
        
        assert health.overall_status == HealthStatus.DEGRADED
        assert health.healthy_checks == 1
        assert health.unhealthy_checks == 1
    
    def test_get_health_critical_unhealthy(self):
        """Test health aggregation with critical unhealthy."""
        engine = HealthEngine()
        
        def healthy_handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        def unhealthy_handler():
            return HealthCheckResult("", "Test", HealthStatus.UNHEALTHY, "Error")
        
        engine.register_check("Healthy", CheckType.CUSTOM, healthy_handler, critical=False)
        engine.register_check("Critical", CheckType.CUSTOM, unhealthy_handler, critical=True)
        
        # Run checks
        for check_id in list(engine._checks.keys()):
            engine.run_check(check_id)
        
        health = engine.get_health()
        
        assert health.overall_status == HealthStatus.UNHEALTHY
        assert health.critical_unhealthy == 1
    
    def test_get_health_unknown(self):
        """Test health aggregation when no checks run."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        engine.register_check("Test", CheckType.CUSTOM, handler)
        
        # Don't run check
        
        health = engine.get_health()
        
        assert health.overall_status == HealthStatus.UNKNOWN
        assert health.unknown_checks == 1
    
    def test_get_check_status(self):
        """Test getting check status."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        engine.run_check(check_id)
        
        status = engine.get_check_status(check_id)
        
        assert status is not None
        assert status.status == HealthStatus.HEALTHY
    
    def test_get_check_status_nonexistent(self):
        """Test getting nonexistent check status."""
        engine = HealthEngine()
        
        status = engine.get_check_status("nonexistent")
        
        assert status is None
    
    def test_get_check_history(self):
        """Test getting check history."""
        engine = HealthEngine()
        
        counter = {"count": 0}
        
        def handler():
            counter["count"] += 1
            return HealthCheckResult(
                "", "Test", HealthStatus.HEALTHY, f"Run {counter['count']}",
            )
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        # Run multiple times
        for _ in range(5):
            engine.run_check(check_id)
        
        history = engine.get_check_history(check_id, limit=3)
        
        assert len(history) == 3
    
    def test_get_check_history_default_limit(self):
        """Test getting check history with default limit."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        for _ in range(15):
            engine.run_check(check_id)
        
        history = engine.get_check_history(check_id)
        
        assert len(history) == 10
    
    def test_enable_check(self):
        """Test enabling check."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        engine.disable_check(check_id)
        engine.enable_check(check_id)
        
        check = engine._checks.get(check_id)
        
        assert check.enabled is True
    
    def test_enable_nonexistent_check(self):
        """Test enabling nonexistent check."""
        engine = HealthEngine()
        
        result = engine.enable_check("nonexistent")
        
        assert result is False
    
    def test_disable_check(self):
        """Test disabling check."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        result = engine.disable_check(check_id)
        
        assert result is True
        
        check = engine._checks.get(check_id)
        
        assert check.enabled is False
    
    def test_disable_nonexistent_check(self):
        """Test disabling nonexistent check."""
        engine = HealthEngine()
        
        result = engine.disable_check("nonexistent")
        
        assert result is False
    
    def test_add_listener(self):
        """Test adding health listener."""
        engine = HealthEngine()
        
        calls = []
        
        def listener(check_id, result):
            calls.append((check_id, result))
        
        engine.add_listener(listener)
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        engine.run_check(check_id)
        
        assert len(calls) == 1
        assert calls[0][0] == check_id
    
    def test_remove_listener(self):
        """Test removing health listener."""
        engine = HealthEngine()
        
        calls = []
        
        def listener(check_id, result):
            calls.append((check_id, result))
        
        engine.add_listener(listener)
        engine.remove_listener(listener)
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        engine.run_check(check_id)
        
        assert len(calls) == 0
    
    def test_remove_nonexistent_listener(self):
        """Test removing nonexistent listener."""
        engine = HealthEngine()
        
        def listener(check_id, result):
            pass
        
        result = engine.remove_listener(listener)
        
        assert result is False
    
    def test_reset_check_failures(self):
        """Test resetting check failures."""
        engine = HealthEngine()
        
        def failing_handler():
            raise RuntimeError("Fail")
        
        check_id = engine.register_check("Failing", CheckType.CUSTOM, failing_handler)
        
        # Cause failures
        for _ in range(3):
            engine.run_check(check_id)
        
        check = engine._checks.get(check_id)
        
        assert check.consecutive_failures == 3
        
        # Reset
        result = engine.reset_check_failures(check_id)
        
        assert result is True
        assert check.consecutive_failures == 0
    
    def test_reset_nonexistent_check_failures(self):
        """Test resetting failures for nonexistent check."""
        engine = HealthEngine()
        
        result = engine.reset_check_failures("nonexistent")
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting health statistics."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        engine.run_check(check_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_checks"] == 1
        assert stats["total_checks_run"] == 1
        assert stats["total_healthy"] == 1
    
    def test_statistics_by_check(self):
        """Test statistics by check."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        for _ in range(5):
            engine.run_check(check_id)
        
        stats = engine.get_statistics()
        
        assert stats["by_check"][check_id] == 5
    
    def test_clear_history_specific_check(self):
        """Test clearing history for specific check."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        for _ in range(10):
            engine.run_check(check_id)
        
        count = engine.clear_history(check_id)
        
        assert count == 10
        
        history = engine.get_check_history(check_id, limit=100)
        
        assert len(history) == 0
    
    def test_clear_history_all(self):
        """Test clearing all history."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check1 = engine.register_check("Test 1", CheckType.CUSTOM, handler)
        check2 = engine.register_check("Test 2", CheckType.CUSTOM, handler)
        
        for _ in range(5):
            engine.run_check(check1)
            engine.run_check(check2)
        
        count = engine.clear_history()
        
        assert count == 10
    
    def test_clear_history_empty(self):
        """Test clearing empty history."""
        engine = HealthEngine()
        
        count = engine.clear_history()
        
        assert count == 0
    
    def test_clear_history_nonexistent_check(self):
        """Test clearing history for nonexistent check."""
        engine = HealthEngine()
        
        count = engine.clear_history("nonexistent")
        
        assert count == 0
    
    def test_health_status_enum_values(self):
        """Test health status enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"
    
    def test_check_type_enum_values(self):
        """Test check type enum values."""
        assert CheckType.HTTP.value == "http"
        assert CheckType.TCP.value == "tcp"
        assert CheckType.DATABASE.value == "database"
        assert CheckType.CACHE.value == "cache"
        assert CheckType.CUSTOM.value == "custom"
        assert CheckType.MEMORY.value == "memory"
        assert CheckType.DISK.value == "disk"
    
    def test_register_check_critical_flag(self):
        """Test registering check with critical flag."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler, critical=False)
        
        check = engine._checks.get(check_id)
        
        assert check.critical is False
    
    def test_register_check_interval_seconds(self):
        """Test registering check with custom interval."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check(
            "Test", CheckType.CUSTOM, handler, interval_seconds=120,
        )
        
        check = engine._checks.get(check_id)
        
        assert check.interval_seconds == 120
    
    def test_run_check_dependency_unhealthy(self):
        """Test that check fails when dependency is unhealthy."""
        engine = HealthEngine()
        
        def healthy_handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        def unhealthy_handler():
            return HealthCheckResult("", "Test", HealthStatus.UNHEALTHY, "Error")
        
        dep_id = engine.register_check("Dependency", CheckType.CUSTOM, unhealthy_handler)
        
        check_id = engine.register_check(
            name="Dependent",
            check_type=CheckType.CUSTOM,
            handler=healthy_handler,
            dependencies=[dep_id],
        )
        
        # Run dependency first
        engine.run_check(dep_id)
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.UNHEALTHY
        assert "Dependencies" in result.message
    
    def test_get_statistics_enabled_checks(self):
        """Test that statistics track enabled checks."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check1 = engine.register_check("Enabled", CheckType.CUSTOM, handler)
        check2 = engine.register_check("Disabled", CheckType.CUSTOM, handler)
        
        engine.disable_check(check2)
        
        stats = engine.get_statistics()
        
        assert stats["enabled_checks"] == 1
    
    def test_get_statistics_critical_checks(self):
        """Test that statistics track critical checks."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        engine.register_check("Critical", CheckType.CUSTOM, handler, critical=True)
        engine.register_check("NonCritical", CheckType.CUSTOM, handler, critical=False)
        
        stats = engine.get_statistics()
        
        assert stats["critical_checks"] == 1
    
    def test_health_aggregation_timestamp(self):
        """Test that aggregation has timestamp."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        engine.run_check(check_id)
        
        health = engine.get_health()
        
        assert health.timestamp is not None
    
    def test_check_created_at_set(self):
        """Test that check created_at is set."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        check = engine._checks.get(check_id)
        
        assert check.created_at is not None
    
    def test_register_check_id_unique(self):
        """Test that check IDs are unique."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        ids = set()
        for i in range(50):
            check_id = engine.register_check(f"Test {i}", CheckType.CUSTOM, handler)
            ids.add(check_id)
        
        assert len(ids) == 50
    
    def test_multiple_checks_independent(self):
        """Test that multiple checks are independent."""
        engine = HealthEngine()
        
        counter = {"count": 0}
        
        def handler():
            counter["count"] += 1
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, f"Run {counter['count']}")
        
        check1 = engine.register_check("Check 1", CheckType.CUSTOM, handler)
        check2 = engine.register_check("Check 2", CheckType.CUSTOM, handler)
        
        engine.run_check(check1)
        engine.run_check(check2)
        
        result1 = engine.get_check_status(check1)
        result2 = engine.get_check_status(check2)
        
        assert result1.message == "Run 1"
        assert result2.message == "Run 2"
    
    def test_check_history_limited_to_100(self):
        """Test that check history is limited to 100 entries."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        for _ in range(150):
            engine.run_check(check_id)
        
        history = engine._history[check_id]
        
        assert len(history) == 100
    
    def test_statistics_total_degraded(self):
        """Test that statistics track degraded results."""
        engine = HealthEngine()
        
        def degraded_handler():
            return HealthCheckResult("", "Test", HealthStatus.DEGRADED, "Warning")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, degraded_handler)
        
        engine.run_check(check_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_degraded"] == 1
    
    def test_statistics_total_unhealthy(self):
        """Test that statistics track unhealthy results."""
        engine = HealthEngine()
        
        def unhealthy_handler():
            return HealthCheckResult("", "Test", HealthStatus.UNHEALTHY, "Error")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, unhealthy_handler)
        
        engine.run_check(check_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_unhealthy"] == 1
    
    def test_check_to_dict_with_last_result(self):
        """Test check serialization with last result."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        engine.run_check(check_id)
        
        check = engine._checks.get(check_id)
        
        d = check.to_dict()
        
        assert d["last_result"] is not None
        assert d["last_result"]["status"] == "healthy"
    
    def test_check_to_dict_without_last_result(self):
        """Test check serialization without last result."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        # Don't run check
        
        check = engine._checks.get(check_id)
        
        d = check.to_dict()
        
        assert d["last_result"] is None
    
    def test_run_check_nonexistent(self):
        """Test running nonexistent check."""
        engine = HealthEngine()
        
        result = engine.run_check("nonexistent")
        
        assert result is None
    
    def test_get_health_empty(self):
        """Test health aggregation with no checks."""
        engine = HealthEngine()
        
        health = engine.get_health()
        
        assert health.overall_status == HealthStatus.UNKNOWN
        assert health.total_checks == 0
    
    def test_listener_exception_handled(self):
        """Test that listener exceptions are handled."""
        engine = HealthEngine()
        
        def failing_listener(check_id, result):
            raise RuntimeError("Listener error")
        
        def working_listener(check_id, result):
            working_listener.called = True
        
        working_listener.called = False
        
        engine.add_listener(failing_listener)
        engine.add_listener(working_listener)
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        # Should not raise
        engine.run_check(check_id)
        
        # Working listener should still be called
        assert working_listener.called is True
    
    def test_check_dependencies_empty(self):
        """Test check with empty dependencies list."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check(
            "Test", CheckType.CUSTOM, handler, dependencies=[],
        )
        
        result = engine.run_check(check_id)
        
        assert result is not None
        assert result.status == HealthStatus.HEALTHY
    
    def test_check_thresholds_empty(self):
        """Test check with empty thresholds dict."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check(
            "Test", CheckType.CUSTOM, handler, thresholds={},
        )
        
        check = engine._checks.get(check_id)
        
        assert check.thresholds == {}
    
    def test_health_result_metadata_empty_by_default(self):
        """Test that health result metadata is empty by default."""
        result = HealthCheckResult(
            check_id="hc_test",
            name="Test",
            status=HealthStatus.HEALTHY,
            message="OK",
        )
        
        assert result.metadata == {}
    
    def test_health_check_dependencies_empty_by_default(self):
        """Test that health check dependencies are empty by default."""
        check = HealthCheck(
            check_id="hc_test",
            name="Test",
            check_type=CheckType.CUSTOM,
            handler=None,
        )
        
        assert check.dependencies == []
    
    def test_health_check_thresholds_empty_by_default(self):
        """Test that health check thresholds are empty by default."""
        check = HealthCheck(
            check_id="hc_test",
            name="Test",
            check_type=CheckType.CUSTOM,
            handler=None,
        )
        
        assert check.thresholds == {}
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = HealthEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_checks_run"] == 0
        assert stats["total_checks"] == 0
        assert stats["enabled_checks"] == 0
        assert stats["critical_checks"] == 0
    
    def test_check_consecutive_failures_initial(self):
        """Test that consecutive failures start at 0."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        check = engine._checks.get(check_id)
        
        assert check.consecutive_failures == 0
    
    def test_health_aggregation_checks_list(self):
        """Test that aggregation includes checks list."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        engine.run_check(check_id)
        
        health = engine.get_health()
        
        assert len(health.checks) == 1
        assert health.checks[0].name == "Test"
    
    def test_run_check_updates_statistics(self):
        """Test that run_check updates statistics."""
        engine = HealthEngine()
        
        def handler():
            return HealthCheckResult("", "Test", HealthStatus.HEALTHY, "OK")
        
        check_id = engine.register_check("Test", CheckType.CUSTOM, handler)
        
        engine.run_check(check_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_checks_run"] == 1
        assert stats["total_healthy"] == 1
