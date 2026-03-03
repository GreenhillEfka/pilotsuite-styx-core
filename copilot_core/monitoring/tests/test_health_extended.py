"""Extended tests for monitoring health module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from unittest.mock import patch as mock_patch
import asyncio


class TestHealthCheckerExtended:
    """Extended health check tests."""
    
    @pytest.mark.asyncio
    async def test_check_library_available(self):
        """Test library availability check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        # Test with built-in library
        result = checker._check_library("os")
        assert result is True
        
        # Test with non-existent library
        result = checker._check_library("nonexistent_library_xyz")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_module_import(self):
        """Test internal module check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        # Test with built-in module
        result = checker._check_module("os")
        assert result is True
        
        # Test with non-existent module
        result = checker._check_module("nonexistent_module_xyz")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_storage_path(self):
        """Test storage path check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        
        # Test with existing path
        result = checker._check_storage_path("/tmp")
        assert result["exists"] is True
        
        # Test with non-existing path
        result = checker._check_storage_path("/nonexistent_path_xyz_123")
        assert result["exists"] is False
    
    @pytest.mark.asyncio
    async def test_get_system_health(self):
        """Test system health metrics."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        result = await checker.get_system_health()
        
        assert "status" in result
        assert "metrics" in result
        assert "cpu_percent" in result["metrics"]
        assert "memory_percent" in result["metrics"]
        assert "disk_percent" in result["metrics"]
    
    @pytest.mark.asyncio
    async def test_get_system_health_with_mock(self):
        """Test system health with mocked psutil."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        
        mock_cpu = MagicMock(return_value=50.0)
        mock_mem = MagicMock(percent=60.0, available=8000000000, total=16000000000)
        mock_disk = MagicMock(percent=70.0, free=30000000000, total=100000000000)
        
        with mock_patch('psutil.cpu_percent', mock_cpu):
            with mock_patch('psutil.virtual_memory', lambda: mock_mem):
                with mock_patch('psutil.disk_usage', lambda p: mock_disk):
                    result = await checker.get_system_health()
                    
                    assert result["metrics"]["cpu_percent"] == 50.0
                    assert result["metrics"]["memory_percent"] == 60.0
                    assert result["metrics"]["disk_percent"] == 70.0
    
    @pytest.mark.asyncio
    async def test_check_service_timeout(self):
        """Test service check with timeout."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        result = await checker._check_service("test", "http://invalid.localhost:9999", timeout=1)
        
        assert "reachable" in result
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_get_dependency_health(self):
        """Test dependency health check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        # Use async mock to avoid network calls
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value.status = 200
            result = await checker.get_dependency_health()
        
        assert "status" in result
    
    @pytest.mark.asyncio
    async def test_get_service_health(self):
        """Test external services health check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        result = await checker.get_service_health()
        
        assert "status" in result
    
    @pytest.mark.asyncio
    async def test_get_module_health(self):
        """Test internal modules health check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        result = await checker.get_module_health()
        
        assert "status" in result
        assert "modules" in result
    
    @pytest.mark.asyncio
    async def test_get_storage_health(self):
        """Test storage health check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        result = await checker.get_storage_health()
        
        assert "status" in result
    
    @pytest.mark.asyncio
    async def test_get_quick_health(self):
        """Test quick health check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        result = await checker.get_quick_health()
        
        assert "status" in result
    
    @pytest.mark.asyncio
    async def test_full_health_check(self):
        """Test full health check."""
        from copilot_core.monitoring.health import HealthChecker
        
        checker = HealthChecker()
        result = await checker.full_health_check()
        
        assert "status" in result
        assert "timestamp" in result
        assert "components" in result
