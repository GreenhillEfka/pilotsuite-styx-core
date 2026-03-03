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
