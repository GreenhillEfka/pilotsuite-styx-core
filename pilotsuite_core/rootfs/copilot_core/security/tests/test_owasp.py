"""Tests for security owasp_middleware module."""
import pytest


class TestOWASPMiddleware:
    """Test OWASP middleware."""
    
    def test_owasp_middleware_import(self):
        """Test OWASP middleware can be imported."""
        try:
            from copilot_core.security.owasp_middleware import OWASPMiddleware
            assert OWASPMiddleware is not None
        except ImportError:
            pytest.skip("flask not installed")
    
    def test_owasp_middleware_available(self):
        """Test OWASP_AVAILABLE flag."""
        from copilot_core.security import OWASP_AVAILABLE
        # Just verify the flag exists
        assert isinstance(OWASP_AVAILABLE, bool)


class TestOWASPFunctions:
    """Test OWASP module functions."""
    
    def test_validate_url_function(self):
        """Test validate_url function exists."""
        try:
            from copilot_core.security.owasp_middleware import validate_url
            assert callable(validate_url)
        except ImportError:
            pytest.skip("flask not installed")
    
    def test_check_injection_function(self):
        """Test check_injection function exists."""
        try:
            from copilot_core.security.owasp_middleware import check_injection
            assert callable(check_injection)
        except ImportError:
            pytest.skip("flask not installed")
    
    def test_require_role_function(self):
        """Test require_role function exists."""
        try:
            from copilot_core.security.owasp_middleware import require_role
            assert callable(require_role)
        except ImportError:
            pytest.skip("flask not installed")
