#!/usr/bin/env python3
"""
Tests for dev surface observability module.
"""

import unittest
import json
import tempfile
import os
from datetime import datetime, timezone
from unittest.mock import patch, Mock

from copilot_core.dev_surface.service import DevSurfaceService
from copilot_core.dev_surface.models import DevLogEntry, ErrorSummary, SystemHealth


class TestDevLogEntry(unittest.TestCase):
    """Test DevLogEntry data model."""
    
    def test_create_entry(self):
        """Test creating a log entry."""
        entry = DevLogEntry.create("INFO", "test_module", "Test message", 
                                   context={"key": "value"})
        
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.module, "test_module")
        self.assertEqual(entry.message, "Test message")
        self.assertEqual(entry.context, {"key": "value"})
        self.assertIsNotNone(entry.timestamp)
        
        # Check timestamp format (ISO 8601)
        datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
    
    def test_to_dict(self):
        """Test serializing to dictionary."""
        entry = DevLogEntry.create("ERROR", "test", "Error message", 
                                   error_type="ValueError",
                                   stack_trace="Traceback...")
        
        data = entry.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["level"], "ERROR")
        self.assertEqual(data["module"], "test")
        self.assertEqual(data["error_type"], "ValueError")


class TestErrorSummary(unittest.TestCase):
    """Test ErrorSummary data model."""
    
    def test_empty_summary(self):
        """Test empty error summary."""
        summary = ErrorSummary()
        self.assertIsNone(summary.last_error)
        self.assertEqual(summary.error_counts, {})
        self.assertEqual(summary.total_errors_24h, 0)
    
    def test_to_dict_with_error(self):
        """Test serializing with error data."""
        entry = DevLogEntry.create("ERROR", "test", "Test error")
        summary = ErrorSummary(
            last_error=entry,
            error_counts={"ValueError": 3, "TypeError": 1},
            total_errors_24h=4,
            most_frequent_error="ValueError"
        )
        
        data = summary.to_dict()
        self.assertEqual(data["total_errors_24h"], 4)
        self.assertEqual(data["most_frequent_error"], "ValueError")
        self.assertIsInstance(data["last_error"], dict)


class TestSystemHealth(unittest.TestCase):
    """Test SystemHealth data model."""
    
    def test_create_current(self):
        """Test creating current system health."""
        health = SystemHealth.create_current(
            memory_usage_mb=128.5,
            brain_graph_nodes=42,
            status="healthy"
        )
        
        self.assertEqual(health.memory_usage_mb, 128.5)
        self.assertEqual(health.brain_graph_nodes, 42)
        self.assertEqual(health.status, "healthy")
        self.assertGreater(health.uptime_seconds, 0)
        
        # Check timestamp
        datetime.fromisoformat(health.timestamp.replace('Z', '+00:00'))


class TestDevSurfaceService(unittest.TestCase):
    """Test DevSurfaceService core functionality."""
    
    def setUp(self):
        """Set up test service."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test_logs.jsonl")
        self.service = DevSurfaceService(
            max_log_entries=10,
            log_file_path=self.log_file
        )
    
    def tearDown(self):
        """Clean up temp files."""
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
        os.rmdir(self.temp_dir)
    
    def test_basic_logging(self):
        """Test basic log entry creation."""
        entry = self.service.info("test_module", "Test message")
        
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.module, "test_module")
        self.assertEqual(entry.message, "Test message")
        
        # Should be in memory store
        logs = self.service.get_recent_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Test message")
    
    def test_error_logging(self):
        """Test error logging with exception."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            self.service.error("test_module", "Something failed", error=e)
        
        # Check error tracking
        error_summary = self.service.get_error_summary()
        self.assertEqual(error_summary.total_errors_24h, 1)
        self.assertEqual(error_summary.error_counts.get("ValueError"), 1)
        self.assertIsNotNone(error_summary.last_error)
        self.assertEqual(error_summary.most_frequent_error, "ValueError")
    
    def test_log_level_filtering(self):
        """Test filtering logs by level."""
        self.service.debug("test", "Debug message")
        self.service.info("test", "Info message")
        self.service.warn("test", "Warning message")
        self.service.error("test", "Error message")
        
        # Get only errors
        error_logs = self.service.get_recent_logs(level_filter="ERROR")
        self.assertEqual(len(error_logs), 1)
        self.assertEqual(error_logs[0]["message"], "Error message")
        
        # Get warnings and errors
        warn_logs = self.service.get_recent_logs(level_filter="WARN") 
        self.assertEqual(len(warn_logs), 1)
        self.assertEqual(warn_logs[0]["message"], "Warning message")
    
    def test_log_limit(self):
        """Test log entry limit enforcement."""
        # Add more entries than max_log_entries (10)
        for i in range(15):
            self.service.info("test", f"Message {i}")
        
        logs = self.service.get_recent_logs()
        self.assertEqual(len(logs), 10)  # Should not exceed max
        
        # Should contain the last 10 messages
        self.assertEqual(logs[-1]["message"], "Message 14")
        self.assertEqual(logs[0]["message"], "Message 5")
    
    def test_file_persistence(self):
        """Test log persistence to file."""
        self.service.info("test", "Persistent message")
        
        # Check file was created and contains entry
        self.assertTrue(os.path.exists(self.log_file))
        
        with open(self.log_file, 'r') as f:
            line = f.readline().strip()
            entry_data = json.loads(line)
            self.assertEqual(entry_data["message"], "Persistent message")
    
    def test_init_falls_back_when_log_dir_unwritable(self):
        """Test fallback path when configured log directory is not writable."""
        fallback_dir = tempfile.mkdtemp()
        try:
            with patch("copilot_core.dev_surface.service.os.makedirs") as mock_makedirs:
                mock_makedirs.side_effect = [PermissionError("denied"), None]
                with patch.dict(os.environ, {"COPILOT_DEV_LOG_DIR": fallback_dir}):
                    service = DevSurfaceService()
            self.assertTrue(service.log_file_path.startswith(fallback_dir))
            self.assertEqual(mock_makedirs.call_count, 2)
        finally:
            os.rmdir(fallback_dir)
    
    def test_system_health(self):
        """Test system health reporting."""
        # Mock brain graph service
        mock_brain_service = Mock()
        mock_brain_service.get_stats.return_value = {
            "total_nodes": 42,
            "total_edges": 15
        }
        
        health = self.service.get_system_health(mock_brain_service)
        
        self.assertEqual(health.brain_graph_nodes, 42)
        self.assertEqual(health.brain_graph_edges, 15)
        self.assertIn(health.status, ["healthy", "degraded", "error"])
    
    def test_events_processed_tracking(self):
        """Test event processing metrics."""
        self.service.increment_events_processed(5)
        self.service.increment_events_processed(3)
        
        health = self.service.get_system_health()
        self.assertEqual(health.events_processed_24h, 8)
    
    def test_clear_logs(self):
        """Test clearing all logs and counters."""
        # Add some entries and errors
        self.service.info("test", "Info message")
        self.service.error("test", "Error message")
        self.service.increment_events_processed(10)
        
        # Verify they exist
        self.assertEqual(len(self.service.get_recent_logs()), 2)
        self.assertEqual(self.service.get_error_summary().total_errors_24h, 1)
        
        # Clear and verify
        self.service.clear_logs()
        self.assertEqual(len(self.service.get_recent_logs()), 0)
        self.assertEqual(self.service.get_error_summary().total_errors_24h, 0)
        self.assertEqual(self.service.get_system_health().events_processed_24h, 0)
    
    def test_export_diagnostics(self):
        """Test comprehensive diagnostics export."""
        self.service.info("test", "Test message")
        self.service.error("test", "Test error")
        
        diagnostics = self.service.export_diagnostics()
        
        self.assertIn("timestamp", diagnostics)
        self.assertIn("system_health", diagnostics)
        self.assertIn("error_summary", diagnostics)
        self.assertIn("recent_logs", diagnostics)
        self.assertIn("version", diagnostics)
        
        # Check structure
        self.assertIsInstance(diagnostics["system_health"], dict)
        self.assertIsInstance(diagnostics["recent_logs"], list)
        self.assertEqual(len(diagnostics["recent_logs"]), 2)


if __name__ == '__main__':
    unittest.main()
