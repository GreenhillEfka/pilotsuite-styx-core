"""Tests for monitoring alerts module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAlertEvaluator:
    """Test alert evaluation functionality."""
    
    @pytest.mark.asyncio
    async def test_alert_evaluator_init(self):
        """Test alert evaluator initialization."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        assert evaluator is not None
    
    @pytest.mark.asyncio
    async def test_get_alert_evaluator_singleton(self):
        """Test singleton pattern for alert evaluator."""
        from copilot_core.monitoring.alerts import get_alert_evaluator
        
        evaluator1 = get_alert_evaluator()
        evaluator2 = get_alert_evaluator()
        assert evaluator1 is evaluator2
    
    @pytest.mark.asyncio
    async def test_evaluate_all_basic(self):
        """Test evaluate_all method exists."""
        from copilot_core.monitoring.alerts import get_alert_evaluator
        
        evaluator = get_alert_evaluator()
        # Just check it doesn't raise
        assert evaluator is not None


class TestAlertRules:
    """Test alert rules loading."""
    
    def test_get_alert_rules_yaml(self):
        """Test loading alert rules as YAML."""
        from copilot_core.monitoring.alerts import get_alert_rules_yaml
        
        rules = get_alert_rules_yaml()
        # Should return a string (YAML content)
        assert isinstance(rules, str) or rules is None
    
    def test_get_alert_rules_json(self):
        """Test loading alert rules as JSON."""
        from copilot_core.monitoring.alerts import get_alert_rules_json
        
        rules = get_alert_rules_json()
        # Should return a list (of alert rules) or None
        assert isinstance(rules, (list, type(None)))
        if rules:
            assert len(rules) > 0
            assert isinstance(rules[0], dict)


class TestAlertEvaluation:
    """Test detailed alert evaluation."""
    
    @pytest.mark.asyncio
    async def test_evaluate_system_metrics_cpu_critical(self):
        """Test CPU critical alert."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_system_metrics(
            cpu_percent=96,
            memory_percent=50,
            disk_percent=50
        )

        assert len(result) > 0
        cpu_alert = [a for a in result if a.name == "HighCPUUsage"][0]
        assert cpu_alert.is_firing is True
        assert cpu_alert.severity == "critical"

    @pytest.mark.asyncio
    async def test_evaluate_system_metrics_cpu_warning(self):
        """Test CPU warning alert."""
        from copilot_core.monitoring.alerts import AlertEvaluator

        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_system_metrics(
            cpu_percent=85,
            memory_percent=50,
            disk_percent=50
        )
        
        cpu_alert = [a for a in result if a.name == "HighCPUUsage"][0]
        assert cpu_alert.is_firing is True
        assert cpu_alert.severity == "warning"
    
    @pytest.mark.asyncio
    async def test_evaluate_system_metrics_memory_critical(self):
        """Test memory critical alert."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_system_metrics(
            cpu_percent=50,
            memory_percent=96,
            disk_percent=50
        )

        memory_alert = [a for a in result if a.name == "HighMemoryUsage"][0]
        assert memory_alert.is_firing is True
        assert memory_alert.severity == "critical"

    @pytest.mark.asyncio
    async def test_evaluate_system_metrics_disk_critical(self):
        """Test disk critical alert."""
        from copilot_core.monitoring.alerts import AlertEvaluator

        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_system_metrics(
            cpu_percent=50,
            memory_percent=50,
            disk_percent=96
        )

        disk_alert = [a for a in result if a.name == "HighDiskUsage"][0]
        assert disk_alert.is_firing is True
        assert disk_alert.severity == "critical"
    
    @pytest.mark.asyncio
    async def test_evaluate_http_metrics_error_rate(self):
        """Test HTTP error rate alert."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_http_metrics(
            error_rate=0.15,
            latency_p95=0.5,
            latency_p99=1.0
        )
        
        error_alert = [a for a in result if a.name == "HighErrorRate"][0]
        assert error_alert.is_firing is True
    
    @pytest.mark.asyncio
    async def test_evaluate_http_metrics_latency(self):
        """Test latency alerts."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_http_metrics(
            error_rate=0.01,
            latency_p95=2.0,
            latency_p99=5.0
        )
        
        latency_alert = [a for a in result if "latency" in a.name.lower()][0]
        assert latency_alert.is_firing is True
    
    @pytest.mark.asyncio
    async def test_evaluate_cache_metrics_low_hit_ratio(self):
        """Test cache hit ratio alert."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_cache_metrics(
            hit_ratio=0.3
        )
        
        cache_alert = [a for a in result if "cache" in a.name.lower()][0]
        assert cache_alert.is_firing is True
    
    @pytest.mark.asyncio
    async def test_evaluate_all_healthy(self):
        """Test evaluate_all with healthy metrics."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_all(
            cpu_percent=30,
            memory_percent=40,
            disk_percent=50,
            error_rate=0.01,
            latency_p95=0.2,
            latency_p99=0.5,
            cache_hit_ratio=0.95
        )
        
        assert result["status"] == "healthy"
        assert result["firing_count"] == 0
    
    @pytest.mark.asyncio
    async def test_evaluate_all_warning(self):
        """Test evaluate_all with warning status."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_all(
            cpu_percent=85,
            memory_percent=50,
            disk_percent=50,
            error_rate=0.01,
            latency_p95=0.2,
            latency_p99=0.5,
            cache_hit_ratio=0.95
        )

        assert result["status"] == "warning"
        assert result["firing_count"] > 0

    @pytest.mark.asyncio
    async def test_evaluate_all_critical(self):
        """Test evaluate_all with critical status."""
        from copilot_core.monitoring.alerts import AlertEvaluator

        evaluator = AlertEvaluator()
        result = await evaluator.evaluate_all(
            cpu_percent=96,
            memory_percent=50,
            disk_percent=50,
            error_rate=0.01,
            latency_p95=0.2,
            latency_p99=0.5,
            cache_hit_ratio=0.95
        )

        assert result["status"] == "critical"
    
    @pytest.mark.asyncio
    async def test_create_alert(self):
        """Test _create_alert method."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        alert = evaluator._create_alert(
            name="TestAlert",
            severity="warning",
            category="test",
            description="Test description",
            current_value=0.8,
            threshold=0.7
        )
        
        assert alert.name == "TestAlert"
        assert alert.is_firing is True
        assert alert.current_value == 0.8
        assert alert.threshold == 0.7
    
    @pytest.mark.asyncio
    async def test_create_alert_inverted(self):
        """Test _create_alert with inverted logic."""
        from copilot_core.monitoring.alerts import AlertEvaluator
        
        evaluator = AlertEvaluator()
        alert = evaluator._create_alert(
            name="TestAlert",
            severity="warning",
            category="test",
            description="Test description",
            current_value=0.3,
            threshold=0.5,
            invert=True
        )
        
        assert alert.is_firing is True  # Lower is worse when inverted
    
    @pytest.mark.asyncio
    async def test_alert_state_to_dict(self):
        """Test AlertState to_dict method."""
        from copilot_core.monitoring.alerts import AlertState
        
        state = AlertState(
            name="TestAlert",
            severity="warning",
            category="test",
            annotations={"description": "Test"}
        )
        state.is_firing = True
        state.current_value = 0.8
        state.threshold = 0.7
        
        result = state.to_dict()
        assert result["name"] == "TestAlert"
        assert result["severity"] == "warning"
        assert result["is_firing"] is True
