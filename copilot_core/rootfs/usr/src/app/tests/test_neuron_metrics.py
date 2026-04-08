"""Tests for Neuron Metrics and Fire-Rate Tracking."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import time

from copilot_core.api.v1.neuron_graph import (
    NeuronGraph,
    NodeMetrics,
    reset_neuron_graph
)


class TestFireRateTracking:
    """Tests for fire-rate tracking functionality."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_fire_rate_initial_zero(self):
        """Test fire rate starts at zero."""
        graph = NeuronGraph()
        node = graph.get_node("context.presence")
        
        assert node.metrics.fire_rate == 0.0
    
    def test_fire_rate_increases_on_fire(self):
        """Test fire rate increases when neuron fires."""
        graph = NeuronGraph()
        
        # Fire multiple times
        for _ in range(5):
            graph.update_node_state("context.presence", active=True, value=0.8, confidence=0.9)
        
        node = graph.get_node("context.presence")
        assert node.metrics.fire_rate > 0.0
    
    def test_fire_rate_tracks_last_60_seconds(self):
        """Test fire rate only counts fires in last 60 seconds."""
        graph = NeuronGraph()
        
        # Fire 10 times
        for _ in range(10):
            graph.update_node_state("state.energy_level", active=True, value=0.9, confidence=0.95)
        
        node = graph.get_node("state.energy_level")
        initial_rate = node.metrics.fire_rate
        
        # Should have recorded fires
        assert initial_rate > 0.0
        assert len(node.metrics.fire_history) > 0
    
    def test_fire_history_limited_to_60(self):
        """Test fire history is limited to 60 entries."""
        metrics = NodeMetrics()
        
        # Record 100 fires
        for i in range(100):
            metrics.record_fire(0.5 + (i % 10) * 0.05)
        
        assert len(metrics.fire_history) <= 60


class TestConfidenceScoring:
    """Tests for confidence scoring per neuron."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_confidence_default_zero(self):
        """Test confidence starts at zero."""
        graph = NeuronGraph()
        node = graph.get_node("mood.focus")
        
        assert node.metrics.confidence == 0.0
    
    def test_confidence_updates_on_state_change(self):
        """Test confidence updates when neuron state changes."""
        graph = NeuronGraph()
        
        graph.update_node_state("context.weather", active=True, value=0.7, confidence=0.88)
        
        node = graph.get_node("context.weather")
        assert node.metrics.confidence == 0.88
    
    def test_confidence_per_neuron(self):
        """Test each neuron has independent confidence."""
        graph = NeuronGraph()
        
        graph.update_node_state("context.presence", active=True, value=0.8, confidence=0.9)
        graph.update_node_state("state.energy_level", active=True, value=0.7, confidence=0.75)
        graph.update_node_state("mood.focus", active=True, value=0.85, confidence=0.92)
        
        presence_conf = graph.get_node("context.presence").metrics.confidence
        energy_conf = graph.get_node("state.energy_level").metrics.confidence
        focus_conf = graph.get_node("mood.focus").metrics.confidence
        
        assert presence_conf == 0.9
        assert energy_conf == 0.75
        assert focus_conf == 0.92
        assert presence_conf != energy_conf != focus_conf
    
    def test_confidence_range(self):
        """Test confidence stays in valid range [0, 1]."""
        graph = NeuronGraph()
        
        # Test various confidence values
        for conf in [0.0, 0.5, 1.0, 0.99, 0.01]:
            graph.update_node_state("state.comfort", active=True, value=0.5, confidence=conf)
            node = graph.get_node("state.comfort")
            assert 0.0 <= node.metrics.confidence <= 1.0


class TestTrendTracking:
    """Tests for trend tracking."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_trend_increasing_for_high_values(self):
        """Test trend is 'increasing' for high values."""
        graph = NeuronGraph()
        
        graph.update_node_state("state.productivity", active=True, value=0.85, confidence=0.9)
        
        node = graph.get_node("state.productivity")
        assert node.metrics.trend == "increasing"
    
    def test_trend_decreasing_for_low_values(self):
        """Test trend is 'decreasing' for low values."""
        graph = NeuronGraph()
        
        graph.update_node_state("state.relaxation", active=False, value=0.15, confidence=0.7)
        
        node = graph.get_node("state.relaxation")
        assert node.metrics.trend == "decreasing"
    
    def test_trend_stable_for_medium_values(self):
        """Test trend is 'stable' for medium values."""
        graph = NeuronGraph()
        
        graph.update_node_state("state.social", active=True, value=0.5, confidence=0.8)
        
        node = graph.get_node("state.social")
        assert node.metrics.trend == "stable"
    
    def test_trend_threshold_boundaries(self):
        """Test trend boundaries at 0.3 and 0.7."""
        graph = NeuronGraph()
        
        # Just below 0.3 -> decreasing
        graph.update_node_state("mood.energy", active=True, value=0.29, confidence=0.8)
        node = graph.get_node("mood.energy")
        assert node.metrics.trend == "decreasing"
        
        # At 0.3 -> stable
        graph.update_node_state("mood.energy", active=True, value=0.3, confidence=0.8)
        node = graph.get_node("mood.energy")
        assert node.metrics.trend == "stable"
        
        # Just above 0.7 -> increasing
        graph.update_node_state("mood.energy", active=True, value=0.71, confidence=0.8)
        node = graph.get_node("mood.energy")
        assert node.metrics.trend == "increasing"


class TestLiveMetrics:
    """Tests for live metrics calculation."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_metrics_to_dict_includes_all_fields(self):
        """Test metrics serialization includes all fields."""
        graph = NeuronGraph()
        
        graph.update_node_state("context.light_level", active=True, value=0.6, confidence=0.85)
        
        node = graph.get_node("context.light_level")
        metrics_dict = node.metrics.to_dict()
        
        assert "fire_rate" in metrics_dict
        assert "confidence" in metrics_dict
        assert "avg_value" in metrics_dict
        assert "trend" in metrics_dict
        assert "last_fire_time" in metrics_dict
    
    def test_metrics_rounded_to_three_decimals(self):
        """Test metrics values are rounded to 3 decimals."""
        graph = NeuronGraph()
        
        graph.update_node_state("mood.calm", active=True, value=0.123456789, confidence=0.987654321)
        
        node = graph.get_node("mood.calm")
        metrics_dict = node.metrics.to_dict()
        
        # Check rounding (confidence is updated, avg_value stays at default 0.0 unless explicitly set)
        assert metrics_dict["confidence"] == 0.988
        # avg_value is separate from node.value, check it's rounded
        assert isinstance(metrics_dict["avg_value"], float)
    
    def test_last_fire_time_isoformat(self):
        """Test last_fire_time is in ISO format."""
        graph = NeuronGraph()
        
        graph.update_node_state("context.time_of_day", active=True, value=0.7, confidence=0.8)
        
        node = graph.get_node("context.time_of_day")
        metrics_dict = node.metrics.to_dict()
        
        if metrics_dict["last_fire_time"] is not None:
            # Should be parseable as ISO format
            datetime.fromisoformat(metrics_dict["last_fire_time"].replace('Z', '+00:00'))


class TestGraphStatsWithMetrics:
    """Tests for graph-level statistics with metrics."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_graph_stats_includes_avg_fire_rate(self):
        """Test graph stats includes average fire rate."""
        graph = NeuronGraph()
        
        # Fire some neurons
        graph.update_node_state("context.presence", active=True, value=0.8, confidence=0.9)
        graph.update_node_state("state.energy_level", active=True, value=0.7, confidence=0.85)
        
        stats = graph.get_stats()
        
        assert "avg_fire_rate" in stats
        assert stats["avg_fire_rate"] >= 0.0
    
    def test_graph_stats_includes_avg_confidence(self):
        """Test graph stats includes average confidence."""
        graph = NeuronGraph()
        
        # Set different confidence values
        graph.update_node_state("context.presence", active=True, value=0.8, confidence=0.9)
        graph.update_node_state("state.energy_level", active=True, value=0.7, confidence=0.7)
        
        stats = graph.get_stats()
        
        assert "avg_confidence" in stats
        # Average should be around 0.8
        assert 0.0 <= stats["avg_confidence"] <= 1.0
    
    def test_graph_stats_layer_breakdown(self):
        """Test graph stats includes per-layer breakdown."""
        graph = NeuronGraph()
        
        # Activate neurons in different layers
        graph.update_node_state("context.presence", active=True, value=0.8, confidence=0.9)
        graph.update_node_state("state.comfort", active=True, value=0.7, confidence=0.85)
        graph.update_node_state("mood.focus", active=True, value=0.85, confidence=0.92)
        
        stats = graph.get_stats()
        
        assert "layers" in stats
        assert "context" in stats["layers"]
        assert "state" in stats["layers"]
        assert "mood" in stats["layers"]
        
        # Check active counts
        assert stats["layers"]["context"]["active"] >= 1
        assert stats["layers"]["state"]["active"] >= 1
        assert stats["layers"]["mood"]["active"] >= 1


class TestMetricsPersistence:
    """Tests for metrics persistence across updates."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_metrics_persist_across_updates(self):
        """Test metrics persist when neuron is updated multiple times."""
        graph = NeuronGraph()
        
        # First update
        graph.update_node_state("context.activity", active=True, value=0.8, confidence=0.9)
        
        # Second update
        graph.update_node_state("context.activity", active=True, value=0.85, confidence=0.92)
        
        node = graph.get_node("context.activity")
        
        # Metrics should still exist
        assert node.metrics.fire_rate >= 0.0
        assert node.metrics.confidence == 0.92
    
    def test_fire_count_accumulates(self):
        """Test fire count accumulates across multiple fires."""
        graph = NeuronGraph()
        
        # Fire 5 times
        for i in range(5):
            graph.update_node_state("mood.energy", active=True, value=0.8, confidence=0.9)
        
        node = graph.get_node("mood.energy")
        
        # Should have recorded multiple fires
        assert len(node.metrics.fire_history) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
