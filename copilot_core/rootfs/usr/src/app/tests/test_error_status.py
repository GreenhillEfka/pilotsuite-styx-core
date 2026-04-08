"""
Tests for Error Status module.

Tests:
- Error history tracking
- API endpoints
"""

import unittest
import time
from copilot_core.error_status import ErrorHistory, register_error, get_error_status, get_error_history


class TestErrorHistory(unittest.TestCase):
    """Test ErrorHistory class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.history = ErrorHistory(max_entries=10, max_per_module=5)
    
    def test_add_error(self):
        """Test adding an error."""
        self.history.add(
            module="test_module",
            function="test_func",
            message="Test error",
            traceback_str="Traceback info"
        )
        
        errors = self.history.get_all(1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["module"], "test_module")
        self.assertEqual(errors[0]["function"], "test_func")
        self.assertEqual(errors[0]["message"], "Test error")
    
    def test_error_timestamp(self):
        """Test error timestamp is set correctly."""
        before = time.time()
        self.history.add("test", "func", "msg")
        after = time.time()
        
        errors = self.history.get_all(1)
        timestamp = errors[0]["timestamp"]
        
        self.assertGreaterEqual(timestamp, before)
        self.assertLessEqual(timestamp, after)
    
    def test_max_entries_limit(self):
        """Test that max_entries limit is enforced."""
        for i in range(15):
            self.history.add("test", f"func_{i}", f"Message {i}")
        
        errors = self.history.get_all(20)
        self.assertEqual(len(errors), 10)  # Only last 10 stored
    
    def test_per_module_limit(self):
        """Test that per-module limit is enforced."""
        for i in range(7):
            self.history.add("test_module", f"func_{i}", f"Message {i}")
        
        errors = self.history.get_by_module("test_module")
        self.assertEqual(len(errors), 5)  # Only last 5 per module
    
    def test_get_by_module(self):
        """Test getting errors by module."""
        self.history.add("module_a", "func", "msg_a")
        self.history.add("module_b", "func", "msg_b")
        
        errors_a = self.history.get_by_module("module_a")
        errors_b = self.history.get_by_module("module_b")
        
        self.assertEqual(len(errors_a), 1)
        self.assertEqual(len(errors_b), 1)
        self.assertEqual(errors_a[0]["message"], "msg_a")
        self.assertEqual(errors_b[0]["message"], "msg_b")
    
    def test_get_summary(self):
        """Test getting error summary."""
        self.history.add("module_a", "func", "msg_a")
        self.history.add("module_a", "func", "msg_a_2")
        self.history.add("module_b", "func", "msg_b")
        
        summary = self.history.get_summary()
        
        self.assertEqual(summary["total_errors"], 3)
        self.assertEqual(summary["modules_with_errors"], 2)
        self.assertEqual(summary["error_counts"]["module_a"], 2)
        self.assertEqual(summary["error_counts"]["module_b"], 1)
        self.assertEqual(len(summary["last_10"]), 3)


class TestRegisterError(unittest.TestCase):
    """Test register_error function."""
    
    def test_register_and_retrieve(self):
        """Test registering an error and retrieving it."""
        register_error(
            module="test_module",
            function="test_func",
            message="Registered error"
        )
        
        history = get_error_history(1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["module"], "test_module")
        self.assertEqual(history[0]["message"], "Registered error")
    
    def test_get_status(self):
        """Test getting error status."""
        register_error("module_a", "func", "msg_a")
        register_error("module_b", "func", "msg_b")
        
        status = get_error_status()
        
        self.assertEqual(status["total_errors"], 2)
        self.assertEqual(status["modules_with_errors"], 2)


if __name__ == "__main__":
    unittest.main()
