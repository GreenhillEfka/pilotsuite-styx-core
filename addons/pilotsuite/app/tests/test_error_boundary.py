"""
Tests for Error Boundary module.

Tests:
- ModuleErrorBoundary decorator
- Error history tracking
- HA connection pool
"""

import unittest
import time
import traceback
from copilot_core.error_boundary import ModuleErrorBoundary, safe_execute


class TestModuleErrorBoundary(unittest.TestCase):
    """Test ModuleErrorBoundary class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.boundary = ModuleErrorBoundary("test_module")
    
    def test_successful_execution(self):
        """Test successful function execution."""
        def safe_func(x):
            return x * 2
        
        result = self.boundary.execute(safe_func, 5)
        self.assertEqual(result, 10)
    
    def test_failed_execution(self):
        """Test failed function execution with error isolation."""
        def failing_func(x):
            raise ValueError("Test error")
        
        result = self.boundary.execute(failing_func, 5)
        self.assertIsNone(result)
        self.assertEqual(self.boundary.error_count, 1)
        self.assertIsNotNone(self.boundary.last_error)
    
    def test_decorator_usage(self):
        """Test using boundary as decorator."""
        @self.boundary.wrap
        def decorated_func():
            return "success"
        
        result = decorated_func()
        self.assertEqual(result, "success")
    
    def test_decorator_with_error(self):
        """Test decorated function with error."""
        @self.boundary.wrap
        def failing_decorated_func():
            raise RuntimeError("Decorated error")
        
        result = failing_decorated_func()
        self.assertIsNone(result)
        self.assertEqual(self.boundary.error_count, 1)
    
    def test_reset(self):
        """Test reset of error counters."""
        def failing_func():
            raise ValueError("Test")
        
        self.boundary.execute(failing_func)
        self.assertEqual(self.boundary.error_count, 1)
        
        self.boundary.reset()
        self.assertEqual(self.boundary.error_count, 0)
        self.assertIsNone(self.boundary.last_error)


class TestSafeExecute(unittest.TestCase):
    """Test safe_execute helper function."""
    
    def test_safe_execution(self):
        """Test successful safe_execute."""
        def add(a, b):
            return a + b
        
        result = safe_execute("math_module", add, 2, 3)
        self.assertEqual(result, 5)
    
    def test_safe_failure(self):
        """Test safe_execute with error."""
        def divide(a, b):
            return a / b
        
        result = safe_execute("math_module", divide, 10, 0)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
