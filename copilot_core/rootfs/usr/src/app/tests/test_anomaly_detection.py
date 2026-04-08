"""
Tests for Anomaly Detection Module

Tests for:
- Feature extraction
- Anomaly detection with Isolation Forest
- Model persistence
- API endpoints
"""

import pytest
import numpy as np
from datetime import datetime, timezone

from copilot_core.ml.feature_extractor import FeatureExtractor, FeatureConfig, create_feature_extractor
from copilot_core.ml.anomaly_detector import (
    AnomalyDetector,
    AnomalyConfig,
    AnomalyLevel,
    AnomalyResult,
    create_anomaly_detector,
)
from copilot_core.ml.model_store import ModelStore, ModelMetadata, TrainingRecord, create_model_store


class TestFeatureExtractor:
    """Tests for FeatureExtractor class."""
    
    def test_extract_basic_features(self):
        """Test basic feature extraction from sensor data."""
        extractor = create_feature_extractor()
        
        # Generate synthetic sensor data (normal distribution)
        np.random.seed(42)
        values = np.random.randn(100) + 10  # Mean 10, std 1
        
        features = extractor.extract(values)
        
        assert features.mean == pytest.approx(10.0, abs=1.0)
        assert features.std > 0
        assert features.min_val < features.mean
        assert features.max_val > features.mean
        assert features.sample_count == 100
    
    def test_extract_percentiles(self):
        """Test percentile calculation."""
        extractor = create_feature_extractor()
        
        values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        features = extractor.extract(values)
        
        assert "p_0_1" in features.percentiles
        assert "p_0_5" in features.percentiles
        assert "p_0_9" in features.percentiles
        
        # Median should be around 5.5
        assert features.percentiles["p_0_5"] == pytest.approx(5.5, abs=1.0)
    
    def test_extract_trend(self):
        """Test trend detection."""
        extractor = create_feature_extractor()
        
        # Upward trend
        values = np.arange(100, dtype=np.float64)
        features = extractor.extract(values)
        
        assert features.trend > 0
        
        # Downward trend
        values = np.arange(100, 0, -1, dtype=np.float64)
        features = extractor.extract(values)
        
        assert features.trend < 0
    
    def test_extract_rate_of_change(self):
        """Test rate of change features."""
        extractor = create_feature_extractor()
        
        # Stable values
        values = np.ones(50)
        features = extractor.extract(values)
        
        assert features.roc_mean == pytest.approx(0.0, abs=0.01)
        assert features.roc_std == pytest.approx(0.0, abs=0.01)
        
        # Rapidly changing values
        values = np.sin(np.linspace(0, 10 * np.pi, 100))
        features = extractor.extract(values)
        
        assert features.roc_std > 0
    
    def test_extract_insufficient_samples(self):
        """Test error handling for insufficient samples."""
        extractor = create_feature_extractor()
        
        values = np.array([1.0, 2.0])  # Too few samples
        
        with pytest.raises(ValueError):
            extractor.extract(values)
    
    def test_extract_with_nan(self):
        """Test handling of NaN values."""
        extractor = create_feature_extractor()
        
        values = np.array([1.0, 2.0, np.nan, 4.0, 5.0, np.nan, 7.0, 8.0, 9.0, 10.0])
        features = extractor.extract(values)
        
        assert features.sample_count == 8  # 2 NaN values removed
        assert not np.isnan(features.mean)
    
    def test_extract_rolling(self):
        """Test rolling window feature extraction."""
        extractor = create_feature_extractor()
        
        values = np.random.randn(200)
        features_list = extractor.extract_rolling(values, window_size=50)
        
        assert len(features_list) == 151  # 200 - 50 + 1
        assert all(f.sample_count == 50 for f in features_list)
    
    def test_extract_multi_sensor(self):
        """Test multi-sensor feature extraction."""
        extractor = create_feature_extractor()
        
        sensor_data = {
            "sensor_1": np.random.randn(100),
            "sensor_2": np.random.randn(100) + 5,
            "sensor_3": np.random.randn(100) - 5,
        }
        
        results = extractor.extract_multi_sensor(sensor_data)
        
        assert len(results) == 3
        assert "sensor_1" in results
        assert "sensor_2" in results
        assert "sensor_3" in results
    
    def test_to_dict(self):
        """Test feature conversion to dictionary."""
        extractor = create_feature_extractor()
        values = np.random.randn(50)
        features = extractor.extract(values)
        
        feature_dict = features.to_dict()
        
        assert "mean" in feature_dict
        assert "std" in feature_dict
        assert "trend" in feature_dict
        assert "autocorrelation" in feature_dict
    
    def test_to_array(self):
        """Test feature conversion to array."""
        extractor = create_feature_extractor()
        values = np.random.randn(50)
        features = extractor.extract(values)
        
        feature_array = features.to_array()
        
        assert isinstance(feature_array, np.ndarray)
        assert len(feature_array) == len(features.to_dict())


class TestAnomalyDetector:
    """Tests for AnomalyDetector class."""
    
    def test_fit_and_detect(self):
        """Test basic fit and detect workflow."""
        detector = create_anomaly_detector(n_estimators=50, contamination=0.05)
        
        # Training data (normal pattern)
        np.random.seed(42)
        training_data = np.random.randn(500) + 10
        
        detector.fit(training_data)
        
        assert detector._is_fitted
        assert detector._n_samples > 0
        
        # Test detection on normal data
        normal_data = np.random.randn(50) + 10
        result = detector.detect(normal_data, sensor_id="test_sensor")
        
        assert isinstance(result, AnomalyResult)
        assert result.sensor_id == "test_sensor"
        assert result.is_anomaly in [True, False]
    
    def test_detect_anomalous_data(self):
        """Test detection of anomalous patterns."""
        detector = create_anomaly_detector(n_estimators=50, contamination=0.05)
        
        # Train on normal data
        np.random.seed(42)
        training_data = np.random.randn(500) + 10
        detector.fit(training_data)
        
        # Anomalous data (sudden spike)
        anomalous_data = np.array([10.0] * 40 + [50.0] * 10)
        result = detector.detect(anomalous_data, sensor_id="spike_sensor")
        
        # Should detect anomaly due to spike
        assert result.is_anomaly or result.score < -0.5
    
    def test_partial_fit(self):
        """Test incremental learning."""
        detector = create_anomaly_detector(n_estimators=50)
        
        # Initial training
        training_data = np.random.randn(200)
        detector.fit(training_data)
        
        initial_samples = detector._n_samples
        
        # Incremental update
        new_data = np.random.randn(100)
        detector.partial_fit(new_data)
        
        assert detector._n_samples > initial_samples
    
    def test_anomaly_level_classification(self):
        """Test anomaly level classification."""
        detector = create_anomaly_detector()
        
        # Test different score ranges
        assert detector._classify_anomaly_level(0.0) == AnomalyLevel.NORMAL
        assert detector._classify_anomaly_level(-0.4) == AnomalyLevel.LOW
        assert detector._classify_anomaly_level(-0.6) == AnomalyLevel.MEDIUM
        assert detector._classify_anomaly_level(-0.8) == AnomalyLevel.HIGH
        assert detector._classify_anomaly_level(-0.95) == AnomalyLevel.CRITICAL
    
    def test_multi_sensor_detection(self):
        """Test multi-sensor anomaly detection."""
        detector = create_anomaly_detector(n_estimators=50)
        
        # Train on multiple sensors
        training_data = {
            "sensor_1": np.random.randn(200),
            "sensor_2": np.random.randn(200) + 5,
        }
        detector.fit(training_data)
        
        # Detect on multiple sensors
        test_data = {
            "sensor_1": np.random.randn(50),
            "sensor_2": np.random.randn(50) + 5,
        }
        results = detector.detect(test_data)
        
        assert len(results) == 2
        sensor_ids = {r.sensor_id for r in results}
        assert "sensor_1" in sensor_ids
        assert "sensor_2" in sensor_ids
    
    def test_sensor_health(self):
        """Test sensor health status."""
        detector = create_anomaly_detector(n_estimators=50)
        
        # Train with dict format (sensor_id -> values)
        training_data = {"test_sensor": np.random.randn(300)}
        detector.fit(training_data)
        
        # Get health
        health = detector.get_sensor_health("test_sensor")
        
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "critical"]
    
    def test_anomaly_history(self):
        """Test anomaly history tracking."""
        detector = create_anomaly_detector(n_estimators=50)
        
        # Train
        detector.fit(np.random.randn(200))
        
        # Detect multiple times
        for i in range(10):
            detector.detect(np.random.randn(30), sensor_id=f"sensor_{i}")
        
        history = detector.get_anomaly_history(limit=5)
        
        assert len(history) <= 5


class TestModelStore:
    """Tests for ModelStore class."""
    
    @pytest.fixture
    def temp_store(self, tmp_path):
        """Create temporary model store."""
        return create_model_store(str(tmp_path))
    
    def test_save_and_load_model(self, temp_store):
        """Test model save and load."""
        model_data = {
            "n_estimators": 100,
            "contamination": 0.05,
            "coefficients": [1.0, 2.0, 3.0],
        }
        
        metadata = ModelMetadata(
            model_id="test_model",
            model_type="test",
            version="1.0.0",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Save
        saved_metadata = temp_store.save_model(
            model_id="test_model",
            version="1.0.0",
            model_data=model_data,
            metadata=metadata,
        )
        
        assert saved_metadata.checksum is not None
        
        # Load
        loaded_data, loaded_metadata = temp_store.load_model("test_model", "1.0.0")
        
        assert loaded_data == model_data
        assert loaded_metadata.model_id == "test_model"
        assert loaded_metadata.version == "1.0.0"
    
    def test_list_versions(self, temp_store):
        """Test version listing."""
        # Save multiple versions
        for version in ["1.0.0", "1.1.0", "2.0.0"]:
            temp_store.save_model(
                model_id="test_model",
                version=version,
                model_data={"version": version},
            )
        
        versions = temp_store.list_versions("test_model")
        
        assert len(versions) == 3
        assert "1.0.0" in versions
        assert "2.0.0" in versions
    
    def test_get_latest_version(self, temp_store):
        """Test latest version retrieval."""
        temp_store.save_model("test_model", "1.0.0", {"v": "1.0.0"})
        temp_store.save_model("test_model", "1.1.0", {"v": "1.1.0"})
        temp_store.save_model("test_model", "2.0.0", {"v": "2.0.0"})
        
        latest = temp_store.get_latest_version("test_model")
        
        assert latest == "2.0.0"
    
    def test_archive_model(self, temp_store):
        """Test model archiving."""
        temp_store.save_model("test_model", "1.0.0", {"v": "1.0.0"})
        
        temp_store.archive_model("test_model", "1.0.0")
        
        _, metadata = temp_store.load_model("test_model", "1.0.0")
        assert metadata.status == "archived"
    
    def test_training_records(self, temp_store):
        """Test training record management."""
        record = TrainingRecord(
            training_id="train_001",
            model_id="test_model",
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            training_samples=1000,
            status="completed",
        )
        
        temp_store.save_training_record(record)
        
        loaded = temp_store.get_training_record("train_001")
        assert loaded is not None
        assert loaded.training_id == "train_001"
    
    def test_store_stats(self, temp_store):
        """Test store statistics."""
        temp_store.save_model("model_1", "1.0.0", {"data": [1, 2, 3]})
        temp_store.save_model("model_2", "1.0.0", {"data": [4, 5, 6]})
        
        stats = temp_store.get_store_stats()
        
        assert stats["total_models"] == 2
        assert stats["total_versions"] == 2


class TestAnomalyAPI:
    """Tests for Anomaly API endpoints (integration tests)."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from copilot_core.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        return app.test_client()
    
    def test_detect_endpoint(self, client):
        """Test anomaly detection endpoint."""
        # First train a model
        train_data = np.random.randn(300).tolist()
        
        client.post("/api/v1/anomaly/train", json={
            "values": train_data,
        })
        
        # Then detect
        test_data = np.random.randn(50).tolist()
        
        response = client.post("/api/v1/anomaly/detect", json={
            "sensor_id": "test_sensor",
            "values": test_data,
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "results" in data
    
    def test_model_status_endpoint(self, client):
        """Test model status endpoint."""
        response = client.get("/api/v1/anomaly/model/status")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "status" in data
    
    def test_sensor_health_endpoint(self, client):
        """Test sensor health endpoint."""
        # Train first
        client.post("/api/v1/anomaly/train", json={
            "values": np.random.randn(200).tolist(),
        })
        
        # Detect to create history
        client.post("/api/v1/anomaly/detect", json={
            "sensor_id": "test_sensor",
            "values": np.random.randn(50).tolist(),
        })
        
        # Get health
        response = client.get("/api/v1/anomaly/sensor/test_sensor/health")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "health" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
