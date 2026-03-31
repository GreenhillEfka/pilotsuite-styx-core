"""Tests for Anomaly Detection Engine — Slice 12."""
import pytest
from copilot_core.anomaly.detection_engine import (
    AnomalyDetectionEngine,
    AnomalyType,
    AnomalySeverity,
    create_anomaly_detection_engine,
)


class TestAnomalyDetectionEngine:
    """Test anomaly detection engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_anomaly_detection_engine()
        assert engine is not None
    
    def test_add_history(self):
        """Test adding values to history."""
        engine = AnomalyDetectionEngine()
        
        # Add 20 values
        for i in range(20):
            engine.add_history("sensor.test", float(i))
        
        # Should have history
        assert "sensor.test" in engine._history
        assert len(engine._history["sensor.test"].values) == 20
    
    def test_detect_value_spike(self):
        """Test detection of value spike."""
        engine = AnomalyDetectionEngine()
        
        # Add normal values (around 100)
        for i in range(20):
            engine.add_history("sensor.test", 100.0 + (i % 5))
        
        # Add spike value (200, far from mean ~102)
        anomalies = engine.detect_anomalies("sensor.test", 200.0)
        
        # Should detect spike
        assert len(anomalies) >= 1
        assert anomalies[0].anomaly_type in (AnomalyType.VALUE_SPIKE, AnomalyType.VALUE_DROP)
    
    def test_detect_value_drop(self):
        """Test detection of value drop."""
        engine = AnomalyDetectionEngine()
        
        # Add normal values (around 100)
        for i in range(20):
            engine.add_history("sensor.test", 100.0 + (i % 5))
        
        # Add drop value (10, far below mean ~102)
        anomalies = engine.detect_anomalies("sensor.test", 10.0)
        
        # Should detect drop
        assert len(anomalies) >= 1
        assert anomalies[0].anomaly_type == AnomalyType.VALUE_DROP
    
    def test_no_anomaly_for_normal_value(self):
        """Test that normal values don't trigger anomalies."""
        engine = AnomalyDetectionEngine()
        
        # Add normal values (around 100)
        for i in range(20):
            engine.add_history("sensor.test", 100.0 + (i % 5))
        
        # Add normal value (102, close to mean)
        anomalies = engine.detect_anomalies("sensor.test", 102.0)
        
        # Should not detect anomaly
        assert len(anomalies) == 0
    
    def test_insufficient_history_no_detection(self):
        """Test that insufficient history doesn't trigger detection."""
        engine = AnomalyDetectionEngine()
        
        # Add only 5 values (less than required 10)
        for i in range(5):
            engine.add_history("sensor.test", float(i))
        
        # Should not detect anomalies (not enough history)
        anomalies = engine.detect_anomalies("sensor.test", 100.0)
        assert len(anomalies) == 0
    
    def test_threshold_breach_detection(self):
        """Test threshold breach detection."""
        engine = AnomalyDetectionEngine()
        
        # Add threshold rule
        engine.add_rule({
            "type": "threshold",
            "entity_id": "sensor.temperature",
            "threshold": 30.0,
            "operator": ">",
            "severity": "high",
        })
        
        # Add value that breaches threshold
        anomalies = engine.detect_anomalies("sensor.temperature", 35.0)
        
        # Should detect threshold breach
        assert len(anomalies) >= 1
        assert anomalies[0].anomaly_type == AnomalyType.THRESHOLD_BREACH
        assert anomalies[0].severity == AnomalySeverity.HIGH
    
    def test_threshold_not_breached(self):
        """Test that values below threshold don't trigger."""
        engine = AnomalyDetectionEngine()
        
        # Add threshold rule
        engine.add_rule({
            "type": "threshold",
            "entity_id": "sensor.temperature",
            "threshold": 30.0,
            "operator": ">",
        })
        
        # Add value below threshold
        anomalies = engine.detect_anomalies("sensor.temperature", 25.0)
        
        # Should not detect anomaly
        assert len(anomalies) == 0
    
    def test_acknowledge_anomaly(self):
        """Test acknowledging an anomaly."""
        engine = AnomalyDetectionEngine()
        
        # Create anomaly
        engine.add_history("sensor.test", 100.0)
        anomalies = engine.detect_anomalies("sensor.test", 200.0)
        
        assert len(anomalies) >= 1
        anomaly_id = anomalies[0].anomaly_id
        
        # Acknowledge
        result = engine.acknowledge_anomaly(anomaly_id)
        assert result is True
        
        # Verify acknowledged
        anomaly_list = engine.get_anomalies(entity_id="sensor.test")
        assert any(a["anomaly_id"] == anomaly_id and a["acknowledged"] for a in anomaly_list)
    
    def test_resolve_anomaly(self):
        """Test resolving an anomaly."""
        engine = AnomalyDetectionEngine()
        
        # Create anomaly
        engine.add_history("sensor.test", 100.0)
        anomalies = engine.detect_anomalies("sensor.test", 200.0)
        
        assert len(anomalies) >= 1
        anomaly_id = anomalies[0].anomaly_id
        
        # Resolve
        result = engine.resolve_anomaly(anomaly_id)
        assert result is True
        
        # Verify resolved (should not appear in unresolved_only list)
        unresolved = engine.get_anomalies(unresolved_only=True)
        assert not any(a["anomaly_id"] == anomaly_id for a in unresolved)
    
    def test_feedback_false_positive(self):
        """Test adding false positive feedback."""
        engine = AnomalyDetectionEngine()
        
        # Create anomaly
        engine.add_history("sensor.test", 100.0)
        anomalies = engine.detect_anomalies("sensor.test", 200.0)
        
        assert len(anomalies) >= 1
        anomaly_id = anomalies[0].anomaly_id
        
        # Add false positive feedback
        initial_threshold = engine._z_score_threshold
        result = engine.add_feedback(anomaly_id, "false_positive")
        assert result is True
        
        # Verify threshold was adjusted
        assert engine._z_score_threshold > initial_threshold
    
    def test_get_anomalies_filtered_by_entity(self):
        """Test filtering anomalies by entity."""
        engine = AnomalyDetectionEngine()
        
        # Create anomalies for different entities
        engine.add_history("sensor.a", 100.0)
        engine.add_history("sensor.b", 100.0)
        
        engine.detect_anomalies("sensor.a", 200.0)
        engine.detect_anomalies("sensor.b", 200.0)
        
        # Filter by entity
        anomalies_a = engine.get_anomalies(entity_id="sensor.a")
        anomalies_b = engine.get_anomalies(entity_id="sensor.b")
        
        assert all(a["entity_id"] == "sensor.a" for a in anomalies_a)
        assert all(a["entity_id"] == "sensor.b" for a in anomalies_b)
    
    def test_get_anomalies_sorted_by_severity(self):
        """Test that anomalies are sorted by severity."""
        engine = AnomalyDetectionEngine()
        
        # Add critical threshold rule
        engine.add_rule({
            "type": "threshold",
            "entity_pattern": "*",
            "threshold": 100.0,
            "operator": ">",
            "severity": "critical",
        })
        
        # Create anomalies with different severities
        engine.add_history("sensor.test", 50.0)
        engine.detect_anomalies("sensor.test", 60.0)  # Statistical, medium
        engine.detect_anomalies("sensor.test", 150.0)  # Threshold, critical
        
        anomalies = engine.get_anomalies()
        
        # Critical should come first
        if len(anomalies) >= 2:
            assert anomalies[0]["severity"] == "critical" or anomalies[0]["deviation_score"] > anomalies[1]["deviation_score"]
    
    def test_anomaly_to_dict(self):
        """Test anomaly serialization."""
        from copilot_core.anomaly.detection_engine import Anomaly
        
        anomaly = Anomaly(
            anomaly_id="test_001",
            anomaly_type=AnomalyType.VALUE_SPIKE,
            severity=AnomalySeverity.HIGH,
            zone_id="zone_living_room",
            module_id="licht_living_room",
            entity_id="light.living_room",
            current_value=200.0,
            expected_value=100.0,
            description="Test anomaly",
        )
        
        d = anomaly.to_dict()
        
        assert d["anomaly_id"] == "test_001"
        assert d["anomaly_type"] == "value_spike"
        assert d["severity"] == "high"
        assert d["zone_id"] == "zone_living_room"
        assert d["entity_id"] == "light.living_room"
        assert d["current_value"] == 200.0
        assert d["expected_value"] == 100.0
        assert d["description"] == "Test anomaly"
        assert d["acknowledged"] is False
        assert d["resolved"] is False


class TestAnomalyHistory:
    """Test anomaly history statistics."""
    
    def test_history_statistics(self):
        """Test history statistics calculation."""
        from copilot_core.anomaly.detection_engine import AnomalyHistory
        
        history = AnomalyHistory(entity_id="sensor.test")
        
        # Add values: 10, 20, 30, 40, 50
        for i in range(1, 6):
            history.update(float(i * 10), "2026-03-31T00:00:00Z")
        
        # Mean should be 30
        assert history.mean == 30.0
        
        # Min should be 10
        assert history.min_value == 10.0
        
        # Max should be 50
        assert history.max_value == 50.0
        
        # Stddev should be ~14.14
        assert abs(history.stddev - 14.14) < 0.1
    
    def test_z_score_calculation(self):
        """Test z-score calculation."""
        from copilot_core.anomaly.detection_engine import AnomalyHistory
        
        history = AnomalyHistory(entity_id="sensor.test")
        
        # Add values around 100
        for i in range(20):
            history.update(100.0 + (i % 5), "2026-03-31T00:00:00Z")
        
        # Value at mean should have z-score ~0
        z_at_mean = history.z_score(102.0)
        assert abs(z_at_mean) < 1.0
        
        # Value far from mean should have high z-score
        z_far = history.z_score(200.0)
        assert abs(z_far) > 3.0
    
    def test_history_trimming(self):
        """Test that history is trimmed to last 1000 values."""
        from copilot_core.anomaly.detection_engine import AnomalyHistory
        
        history = AnomalyHistory(entity_id="sensor.test")
        
        # Add 1500 values
        for i in range(1500):
            history.update(float(i), "2026-03-31T00:00:00Z")
        
        # Should be trimmed to 1000
        assert len(history.values) == 1000
        
        # Should contain last 1000 values (500-1499)
        assert history.values[0] == 500.0
        assert history.values[-1] == 1499.0
