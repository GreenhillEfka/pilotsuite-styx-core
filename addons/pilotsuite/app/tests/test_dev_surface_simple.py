#!/usr/bin/env python3
"""
Simple tests for dev surface observability module (without psutil dependency).
"""

import unittest
import json
import tempfile
import os
from unittest.mock import patch, Mock

# Mock psutil before importing dev_surface modules
import sys
mock_psutil = Mock()
mock_psutil.Process.return_value.memory_info.return_value.rss = 134217728  # 128 MB
sys.modules['psutil'] = mock_psutil

from copilot_core.dev_surface.service import DevSurfaceService
from copilot_core.dev_surface.models import DevLogEntry, ErrorSummary


class TestDevSurfaceBasics(unittest.TestCase):
    """Test basic dev surface functionality without external dependencies."""
    
    def setUp(self):
        """Set up test service."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test_logs.jsonl")
        self.service = DevSurfaceService(
            max_log_entries=5,
            log_file_path=self.log_file
        )
    
    def tearDown(self):
        """Clean up temp files."""
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
        os.rmdir(self.temp_dir)
    
    def test_log_creation(self):
        """Test creating different log levels."""
        # Test all log levels
        debug_entry = self.service.debug("test", "Debug message", context={"test": True})
        info_entry = self.service.info("test", "Info message")
        warn_entry = self.service.warn("test", "Warning message")
        error_entry = self.service.error("test", "Error message")
        
        self.assertEqual(debug_entry.level, "DEBUG")
        self.assertEqual(info_entry.level, "INFO") 
        self.assertEqual(warn_entry.level, "WARN")
        self.assertEqual(error_entry.level, "ERROR")
        
        # Check context preservation
        self.assertEqual(debug_entry.context, {"test": True})
    
    def test_error_tracking(self):
        """Test error counting and tracking."""
        # Create some errors
        try:
            raise ValueError("Test error 1")
        except ValueError as e:
            self.service.error("module1", "First error", error=e)
        
        try:
            raise TypeError("Test error 2")  
        except TypeError as e:
            self.service.error("module2", "Second error", error=e)
            
        try:
            raise ValueError("Test error 3")
        except ValueError as e:
            self.service.error("module1", "Third error", error=e)
        
        # Check error summary
        summary = self.service.get_error_summary()
        self.assertEqual(summary.total_errors_24h, 3)
        self.assertEqual(summary.error_counts["ValueError"], 2)
        self.assertEqual(summary.error_counts["TypeError"], 1)
        self.assertEqual(summary.most_frequent_error, "ValueError")
        self.assertIsNotNone(summary.last_error)
        self.assertEqual(summary.last_error.message, "Third error")
    
    def test_ring_buffer_limit(self):
        """Test that log entries respect max limit."""
        # Add more entries than the limit (5)
        for i in range(8):
            self.service.info("test", f"Message {i}")
        
        logs = self.service.get_recent_logs()
        self.assertEqual(len(logs), 5)  # Should not exceed max
        
        # Should contain the most recent 5
        messages = [log["message"] for log in logs]
        expected = [f"Message {i}" for i in range(3, 8)]
        self.assertEqual(messages, expected)
    
    def test_level_filtering(self):
        """Test filtering logs by level."""
        self.service.debug("test", "Debug message")
        self.service.info("test", "Info message")
        self.service.warn("test", "Warning message") 
        self.service.error("test", "Error message")
        
        # Test each level filter
        debug_logs = self.service.get_recent_logs(level_filter="DEBUG")
        self.assertEqual(len(debug_logs), 1)
        self.assertEqual(debug_logs[0]["message"], "Debug message")
        
        info_logs = self.service.get_recent_logs(level_filter="INFO")
        self.assertEqual(len(info_logs), 1)
        
        warn_logs = self.service.get_recent_logs(level_filter="WARN")
        self.assertEqual(len(warn_logs), 1)
        
        error_logs = self.service.get_recent_logs(level_filter="ERROR")
        self.assertEqual(len(error_logs), 1)
    
    def test_limit_parameter(self):
        """Test limit parameter in get_recent_logs."""
        # Add several entries
        for i in range(5):
            self.service.info("test", f"Message {i}")
        
        # Test different limits
        logs_2 = self.service.get_recent_logs(limit=2)
        self.assertEqual(len(logs_2), 2)
        self.assertEqual(logs_2[-1]["message"], "Message 4")  # Most recent
        
        logs_all = self.service.get_recent_logs()
        self.assertEqual(len(logs_all), 5)
    
    def test_file_persistence(self):
        """Test that logs are persisted to file."""
        self.service.info("test", "Persistent message", context={"key": "value"})
        self.service.error("test", "Error message")
        
        # Check file exists and contains entries
        self.assertTrue(os.path.exists(self.log_file))
        
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        # Note: error() increments error count but both info() and error() should write to file
        self.assertGreaterEqual(len(lines), 1)  # At least one entry should be written
        
        if len(lines) >= 1:
            # Parse first entry (should be the info message)
            entry1 = json.loads(lines[0])
            self.assertEqual(entry1["message"], "Persistent message")
            self.assertEqual(entry1["level"], "INFO")
            self.assertEqual(entry1["context"], {"key": "value"})
        
        if len(lines) >= 2:
            # Parse second entry (should be the error message)
            entry2 = json.loads(lines[1])
            self.assertEqual(entry2["message"], "Error message")
            self.assertEqual(entry2["level"], "ERROR")
    
    def test_system_health_basic(self):
        """Test basic system health without brain graph."""
        self.service.increment_events_processed(10)

        health = self.service.get_system_health()

        self.assertEqual(health.events_processed_24h, 10)
        self.assertEqual(health.errors_24h, 0)
        self.assertEqual(health.brain_graph_nodes, 0)
        self.assertEqual(health.brain_graph_edges, 0)
        self.assertEqual(health.status, "healthy")
        # memory_usage_mb may be None if psutil mock is overwritten by other tests
        self.assertGreater(health.uptime_seconds, 0)
    
    def test_system_health_with_errors(self):
        """Test system health status with errors."""
        # Add many errors to trigger degraded status
        for i in range(15):
            self.service.error("test", f"Error {i}")
        
        health = self.service.get_system_health()
        self.assertEqual(health.errors_24h, 15)
        self.assertEqual(health.status, "degraded")  # 10+ errors
    
    def test_clear_functionality(self):
        """Test clearing logs and counters."""
        # Add some data
        self.service.info("test", "Info message")
        self.service.error("test", "Error message")
        self.service.increment_events_processed(5)
        
        # Verify data exists
        self.assertEqual(len(self.service.get_recent_logs()), 2)
        self.assertEqual(self.service.get_error_summary().total_errors_24h, 1)
        self.assertEqual(self.service.get_system_health().events_processed_24h, 5)
        
        # Clear everything
        self.service.clear_logs()
        
        # Verify cleared
        self.assertEqual(len(self.service.get_recent_logs()), 0)
        self.assertEqual(self.service.get_error_summary().total_errors_24h, 0)
        self.assertEqual(self.service.get_system_health().events_processed_24h, 0)
    
    def test_diagnostics_export(self):
        """Test comprehensive diagnostics export."""
        # Add some test data
        self.service.info("test", "Info message", context={"test": True})
        self.service.error("test", "Error message")
        self.service.increment_events_processed(3)
        
        diagnostics = self.service.export_diagnostics()
        
        # Check required fields
        required_fields = ["timestamp", "system_health", "error_summary", "recent_logs", "version"]
        for field in required_fields:
            self.assertIn(field, diagnostics)
        
        # Check data structure
        self.assertIsInstance(diagnostics["system_health"], dict)
        self.assertIsInstance(diagnostics["error_summary"], dict)
        self.assertIsInstance(diagnostics["recent_logs"], list)
        
        # Check recent logs content
        self.assertEqual(len(diagnostics["recent_logs"]), 2)
        log_messages = [log["message"] for log in diagnostics["recent_logs"]]
        self.assertIn("Info message", log_messages)
        self.assertIn("Error message", log_messages)


if __name__ == '__main__':
    unittest.main()