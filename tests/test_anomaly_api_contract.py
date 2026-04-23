"""Anomaly API Contract Tests — CORE-HARDEN-209"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.anomaly import anomaly_bp
from unittest.mock import patch, MagicMock
from copilot_core.ml.anomaly_detector import AnomalyResult, AnomalyLevel


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(anomaly_bp)
    return app


TS = datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ── Fresh mock factory (called per-test to avoid state pollution ─────────────

def _make_result(sensor_id="sensor_123", score=0.5, is_anomaly=False,
                 level=AnomalyLevel.NORMAL):
    return AnomalyResult(
        sensor_id=sensor_id,
        score=score,
        is_anomaly=is_anomaly,
        level=level,
        features={"mean": 1.0, "std": 0.1},
        contributing_features=["mean", "std"],
        timestamp=TS,
    )


def _make_detector():
    mock = MagicMock()
    mock.detect.return_value = [_make_result()]
    mock.compare.return_value = {
        "left": [_make_result("sensor_1", 0.3)],
        "right": [_make_result("sensor_2", 0.7)],
    }
    mock.get_sensor_health.return_value = {
        "sensor_id": "sensor_123",
        "status": "healthy",
        "anomaly_rate": 0.05,
        "recent_anomalies": 5,
        "total_samples": 1000,
        "stats": {},
    }
    # Real attribute values (not MagicMock children) used in train/status/save/load
    mock._is_fitted = True
    mock._n_samples = 1000
    mock._feature_names = ["mean", "std"]
    mock._sensor_stats = {"sensor_123": {}}
    mock._scaler = None
    mock.config.n_estimators = 100
    mock.config.contamination = 0.05
    mock.config.max_samples = 10000
    mock.config.max_features = 1.0
    mock.config.bootstrap = False
    mock.config.warm_start = False
    mock.fit.return_value = None
    mock.partial_fit.return_value = None
    mock.save_model.return_value = "/data/ml_models/model.pkl"
    mock.load_model.return_value = None  # called with path; set model_dir below
    mock.model_dir = "/data/ml_models"
    return mock


def _make_model_store():
    mock = MagicMock()
    mock.list_versions.return_value = ["1.0.0"]
    mock.get_latest_version.return_value = "1.0.0"
    # load_model returns (model_data, metadata) tuple
    metadata_mock = MagicMock()
    metadata_mock.created_at = "2024-03-01T12:00:00Z"
    metadata_mock.training_samples = 1000
    metadata_mock.status = "active"
    mock.load_model.return_value = ({"n_estimators": 100}, metadata_mock)
    mock.get_stats.return_value = {"total_records": 100, "anomaly_count": 5}
    mock.get_store_stats.return_value = {"total_records": 100, "anomaly_count": 5}
    mock.save_training_record.return_value = None
    mock.compare_models.return_value = {"comparison": {"model_id": "anomaly_detector"}}
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# Detect — POST /anomaly/detect
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyDetect:
    """POST /anomaly/detect."""

    def test_post_detect_single_sensor_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.post(
                "/anomaly/detect",
                json={"sensor_id": "sensor_123", "values": [1.0, 1.1, 0.9]},
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_detect_single_sensor_returns_ok_flag(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.post(
                "/anomaly/detect",
                json={"sensor_id": "sensor_123", "values": [1.0, 1.1, 0.9]},
            )
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_post_detect_multi_sensor_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.post(
                "/anomaly/detect",
                json={
                    "sensors": {
                        "sensor_1": [1.0, 1.1, 0.9],
                        "sensor_2": [2.0, 2.1, 1.9],
                    }
                },
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_detect_returns_results_key(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.post(
                "/anomaly/detect",
                json={"sensor_id": "sensor_123", "values": [1.0, 1.1, 0.9]},
            )
            data = r.get_json()
            assert "results" in data, f"'results' key missing from response: {data}"

    def test_post_detect_missing_values_and_sensors_returns_400(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.post("/anomaly/detect", json={"sensor_id": "sensor_123"})
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_post_detect_invalid_values_type_returns_400(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.post(
                "/anomaly/detect",
                json={"sensor_id": "sensor_123", "values": "not an array"},
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_post_detect_empty_sensors_returns_400(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.post("/anomaly/detect", json={"sensors": {}})
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"


# ─────────────────────────────────────────────────────────────────────────────
# History — GET /anomaly/history
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyHistory:
    """GET /anomaly/history."""

    def test_get_history_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.get("/anomaly/history")
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_history_returns_ok_flag(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.get("/anomaly/history")
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_get_history_with_sensor_filter_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.get("/anomaly/history?sensor_id=sensor_123")
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_history_with_level_filter_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.get("/anomaly/history?level=medium")
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"


# ─────────────────────────────────────────────────────────────────────────────
# Sensor health — GET /anomaly/sensor/<sensor_id>/health
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalySensorHealth:
    """GET /anomaly/sensor/<sensor_id>/health."""

    def test_get_sensor_health_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.get("/anomaly/sensor/sensor_123/health")
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_sensor_health_returns_ok_flag(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.get("/anomaly/sensor/sensor_123/health")
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"


# ─────────────────────────────────────────────────────────────────────────────
# Train — POST /anomaly/train
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyTrain:
    """POST /anomaly/train."""

    def test_post_train_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
                client = app.test_client()
                r = client.post(
                    "/anomaly/train",
                    json={"values": [[1.0, 1.1], [0.9, 1.0]]},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_train_returns_ok_flag(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
                client = app.test_client()
                r = client.post(
                    "/anomaly/train",
                    json={"values": [[1.0, 1.1], [0.9, 1.0]]},
                )
                data = r.get_json()
                assert data.get("ok") is True, f"expected ok=True, got {data}"


# ─────────────────────────────────────────────────────────────────────────────
# Model status — GET /anomaly/model/status
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyModelStatus:
    """GET /anomaly/model/status."""

    def test_get_model_status_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.get("/anomaly/model/status")
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_model_status_returns_ok_flag(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=_make_detector()):
            client = app.test_client()
            r = client.get("/anomaly/model/status")
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"


# ─────────────────────────────────────────────────────────────────────────────
# Model save — POST /anomaly/model/save
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyModelSave:
    """POST /anomaly/model/save."""

    def test_post_model_save_returns_200(self):
        app = _make_app()
        mock = _make_detector()
        mock.save.return_value = "/data/ml_models/model.pkl"
        mock._is_fitted = True
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=mock):
            with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
                client = app.test_client()
                r = client.post("/anomaly/model/save", json={"model_name": "my_model"})
                assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_model_save_returns_ok_flag(self):
        app = _make_app()
        mock = _make_detector()
        mock.save.return_value = "/data/ml_models/model.pkl"
        mock._is_fitted = True
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=mock):
            with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
                client = app.test_client()
                r = client.post("/anomaly/model/save", json={"model_name": "my_model"})
                data = r.get_json()
                assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_post_model_save_unfitted_returns_400(self):
        app = _make_app()
        mock = _make_detector()
        mock._is_fitted = False
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=mock):
            client = app.test_client()
            r = client.post("/anomaly/model/save", json={})
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"


# ─────────────────────────────────────────────────────────────────────────────
# Model load — POST /anomaly/model/load
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyModelLoad:
    """POST /anomaly/model/load."""

    def test_post_model_load_returns_200(self):
        app = _make_app()
        mock = _make_detector()
        mock.load.return_value = {"loaded": True, "model_name": "my_model"}
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=mock):
            with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
                client = app.test_client()
                r = client.post("/anomaly/model/load", json={"model_name": "my_model"})
                assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_model_load_returns_ok_flag(self):
        app = _make_app()
        mock = _make_detector()
        mock.load.return_value = {"loaded": True, "model_name": "my_model"}
        with patch("copilot_core.api.v1.anomaly.get_detector", return_value=mock):
            with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
                client = app.test_client()
                r = client.post("/anomaly/model/load", json={"model_name": "my_model"})
                data = r.get_json()
                assert data.get("ok") is True, f"expected ok=True, got {data}"


# ─────────────────────────────────────────────────────────────────────────────
# Model versions — GET /anomaly/model/versions
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyModelVersions:
    """GET /anomaly/model/versions."""

    def test_get_model_versions_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
            client = app.test_client()
            r = client.get("/anomaly/model/versions")
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_model_versions_returns_ok_flag(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
            client = app.test_client()
            r = client.get("/anomaly/model/versions")
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"


# ─────────────────────────────────────────────────────────────────────────────
# Compare — POST /anomaly/compare
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyCompare:
    """POST /anomaly/compare."""

    def test_post_compare_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
            client = app.test_client()
            r = client.post(
                "/anomaly/compare",
                json={"versions": ["1.0.0", "2.0.0"]},
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_compare_returns_ok_flag(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
            client = app.test_client()
            r = client.post(
                "/anomaly/compare",
                json={"versions": ["1.0.0", "2.0.0"]},
            )
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_post_compare_missing_versions_returns_400(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
            client = app.test_client()
            r = client.post("/anomaly/compare", json={})
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"


# ─────────────────────────────────────────────────────────────────────────────
# Store stats — GET /anomaly/store/stats
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyStoreStats:
    """GET /anomaly/store/stats."""

    def test_get_store_stats_returns_200(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
            client = app.test_client()
            r = client.get("/anomaly/store/stats")
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_store_stats_returns_ok_flag(self):
        app = _make_app()
        with patch("copilot_core.api.v1.anomaly.get_model_store", return_value=_make_model_store()):
            client = app.test_client()
            r = client.get("/anomaly/store/stats")
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"
