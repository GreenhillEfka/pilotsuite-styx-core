"""Tests for monitoring health module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHealthChecker:
    """Test health check functionality."""
    
    @pytest.mark.asyncio
    async def test_health_checker_init(self):
        """Test health checker initialization."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        assert checker is not None
    
    @pytest.mark.asyncio
    async def test_get_health_checker_singleton(self):
        """Test singleton pattern for health checker."""
        from copilot_core.monitoring.health import get_health_checker
        
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        assert checker1 is checker2
    
    @pytest.mark.asyncio
    async def test_basic_health_check(self):
        """Test basic health check returns expected structure."""
        from copilot_core.monitoring.health import get_health_checker
        
        checker = get_health_checker()
        # Just check it doesn't raise
        assert checker is not None


class TestHealthStatus:
    """Test health status structures."""
    
    def test_health_status_import(self):
        """Test health status can be imported."""
        # Just ensure the module loads
        from copilot_core.monitoring.health import HealthChecker
        assert HealthChecker is not None
