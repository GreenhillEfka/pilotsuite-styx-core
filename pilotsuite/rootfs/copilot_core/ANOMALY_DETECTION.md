# Anomaly Detection Module

ML-based anomaly detection for sensor patterns using Isolation Forest algorithm.

## Overview

This module provides unsupervised anomaly detection for time series sensor data, enabling the PilotSuite system to identify:

- Sudden energy consumption spikes
- Unexpected activity patterns
- Anomalous sensor behavior
- Equipment malfunctions

## Architecture

```
copilot_core/
├── ml/
│   ├── __init__.py
│   ├── feature_extractor.py    # Time series feature extraction
│   ├── anomaly_detector.py     # Isolation Forest implementation
│   └── model_store.py          # Model persistence & versioning
└── api/v1/
    └── anomaly.py              # REST API endpoints
```

## Components

### 1. Feature Extractor (`feature_extractor.py`)

Extracts statistical, temporal, and distributional features from sensor time series:

**Statistical Features:**
- Mean, standard deviation, min, max, range
- Percentiles (10th, 25th, 50th, 75th, 90th)
- Skewness and kurtosis

**Temporal Features:**
- Linear trend coefficient
- Lag-1 autocorrelation
- Rate of change (mean, std, max)

**Lag Features:**
- Last N values for pattern recognition

**Usage:**
```python
from copilot_core.ml.feature_extractor import create_feature_extractor

extractor = create_feature_extractor(
    short_window=10,
    medium_window=50,
    long_window=200
)

# Extract features from sensor data
values = [1.2, 1.5, 1.3, 1.8, ...]  # Sensor readings
features = extractor.extract(values)

# Get feature dictionary for ML model
feature_dict = features.to_dict()
```

### 2. Anomaly Detector (`anomaly_detector.py`)

Implements Isolation Forest algorithm for unsupervised anomaly detection:

**Key Features:**
- Isolation Forest with configurable parameters
- Incremental learning via `partial_fit()`
- Anomaly scoring (-1 to 1, where -1 is most anomalous)
- Anomaly level classification (normal, low, medium, high, critical)
- Per-sensor statistics tracking
- Contributing feature analysis

**Anomaly Levels:**
| Level | Score Range | Description |
|-------|-------------|-------------|
| NORMAL | ≥ -0.3 | Within expected range |
| LOW | -0.3 to -0.5 | Slight deviation |
| MEDIUM | -0.5 to -0.7 | Notable anomaly |
| HIGH | -0.7 to -0.9 | Significant anomaly |
| CRITICAL | < -0.9 | Severe anomaly, immediate attention |

**Usage:**
```python
from copilot_core.ml.anomaly_detector import create_anomaly_detector

detector = create_anomaly_detector(
    n_estimators=100,
    contamination=0.05,
    model_dir="/data/ml_models"
)

# Train on historical data
training_data = [/* sensor readings */]
detector.fit(training_data)

# Detect anomalies
result = detector.detect(new_data, sensor_id="sensor_123")

if result.is_anomaly:
    print(f"Anomaly detected! Level: {result.level}")
    print(f"Contributing features: {result.contributing_features}")

# Incremental update
detector.partial_fit(more_data)
```

### 3. Model Store (`model_store.py`)

Provides persistent storage and versioning for ML models:

**Features:**
- Model versioning (semantic versioning)
- Training record tracking
- Model comparison
- Automatic checksums for integrity
- A/B testing support

**Directory Structure:**
```
/data/ml_models/
├── models/
│   ├── anomaly_detector/
│   │   ├── v1.0.0/
│   │   │   ├── model.json
│   │   │   └── metadata.json
│   │   └── v1.1.0/
│   └── feature_extractor/
├── training/
│   └── train_20240301_120000.json
└── registry.json
```

**Usage:**
```python
from copilot_core.ml.model_store import create_model_store

store = create_model_store("/data/ml_models")

# Save model
store.save_model(
    model_id="anomaly_detector",
    version="1.0.0",
    model_data=model_dict,
    metadata=metadata
)

# Load specific version
model_data, metadata = store.load_model("anomaly_detector", "1.0.0")

# List versions
versions = store.list_versions("anomaly_detector")

# Compare versions
comparison = store.compare_models("anomaly_detector", ["1.0.0", "1.1.0"])
```

## API Endpoints

All endpoints are prefixed with `/api/v1/anomaly/` and require authentication.

### Detection

#### `POST /detect`
Detect anomalies in sensor data.

**Request:**
```json
{
  "sensor_id": "sensor_123",
  "values": [1.2, 1.5, 1.3, ...]
}
```

**Response:**
```json
{
  "ok": true,
  "results": [{
    "sensor_id": "sensor_123",
    "score": -0.45,
    "is_anomaly": true,
    "level": "medium",
    "timestamp": "2024-03-01T12:00:00Z",
    "features": {...},
    "contributing_features": ["std", "roc_max"]
  }],
  "critical_count": 0,
  "total_count": 1
}
```

#### `GET /history`
Get anomaly detection history.

**Query Params:**
- `sensor_id` (optional): Filter by sensor
- `level` (optional): Minimum level (normal, low, medium, high, critical)
- `limit` (optional): Max results (default: 100)

#### `GET /sensor/:sensor_id/health`
Get health status for a sensor.

**Response:**
```json
{
  "ok": true,
  "health": {
    "sensor_id": "sensor_123",
    "status": "healthy",
    "anomaly_rate": 0.05,
    "recent_anomalies": 5,
    "total_samples": 1000
  }
}
```

### Training

#### `POST /train`
Train or update the anomaly detection model.

**Request:**
```json
{
  "values": [/* training data */],
  "incremental": true,
  "config": {
    "n_estimators": 100,
    "contamination": 0.05
  }
}
```

**Response:**
```json
{
  "ok": true,
  "training_id": "train_20240301_120000",
  "samples": 1000,
  "duration_seconds": 2.5,
  "model_status": "fitted"
}
```

### Model Management

#### `GET /model/status`
Get current model status and configuration.

#### `POST /model/save`
Save model to disk.

**Request:**
```json
{
  "version": "1.0.0",
  "metadata": {
    "description": "Production model",
    "tags": ["production", "v1"]
  }
}
```

#### `POST /model/load`
Load model from disk.

#### `GET /model/versions`
List all available model versions.

#### `POST /compare`
Compare multiple model versions.

#### `GET /store/stats`
Get model store statistics.

## Integration Example

### Basic Workflow

```python
import requests

API_BASE = "http://localhost:8909/api/v1"
AUTH_TOKEN = "your-token"

headers = {"X-Auth-Token": AUTH_TOKEN}

# 1. Train initial model
training_data = get_historical_sensor_data()  # Your data source

response = requests.post(
    f"{API_BASE}/anomaly/train",
    json={"values": training_data},
    headers=headers
)

# 2. Detect anomalies in real-time
def check_sensor(sensor_id, values):
    response = requests.post(
        f"{API_BASE}/anomaly/detect",
        json={"sensor_id": sensor_id, "values": values},
        headers=headers
    )
    
    result = response.json()["results"][0]
    
    if result["level"] == "critical":
        send_alert(sensor_id, result)
    elif result["is_anomaly"]:
        log_anomaly(sensor_id, result)
    
    return result

# 3. Periodic model updates
def update_model():
    new_data = get_recent_sensor_data()
    requests.post(
        f"{API_BASE}/anomaly/train",
        json={"values": new_data, "incremental": True},
        headers=headers
    )
    
    # Save new version
    requests.post(
        f"{API_BASE}/anomaly/model/save",
        json={"version": get_new_version()},
        headers=headers
    )
```

### Alert Integration

```python
from copilot_core.notifications import send_alert

def handle_anomaly(result):
    if result.level == AnomalyLevel.CRITICAL:
        send_alert(
            title=f"Critical Anomaly: {result.sensor_id}",
            message=f"Anomaly score: {result.score:.2f}\n"
                   f"Contributing factors: {', '.join(result.contributing_features)}",
            priority="high"
        )
    elif result.level == AnomalyLevel.HIGH:
        send_alert(
            title=f"High Anomaly: {result.sensor_id}",
            message=f"Anomaly detected with score {result.score:.2f}",
            priority="medium"
        )
```

## Configuration

### Detector Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_estimators` | 100 | Number of trees in forest |
| `contamination` | 0.05 | Expected proportion of anomalies |
| `max_samples` | "auto" | Samples to draw for each tree |
| `max_features` | 1.0 | Features to draw for each tree |
| `bootstrap` | False | Sample with replacement |
| `warm_start` | True | Enable incremental learning |

### Feature Extraction

| Parameter | Default | Description |
|-----------|---------|-------------|
| `short_window` | 10 | Short-term rolling window |
| `medium_window` | 50 | Medium-term rolling window |
| `long_window` | 200 | Long-term rolling window |
| `max_lag` | 10 | Maximum lag for lag features |

### Thresholds

| Level | Threshold | Use Case |
|-------|-----------|----------|
| Low | -0.3 | Minor deviations, logging only |
| Medium | -0.5 | Notable anomalies, monitoring |
| High | -0.7 | Significant issues, alerts |
| Critical | -0.9 | Severe problems, immediate action |

## Testing

Run tests with pytest:

```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
pytest -v tests/test_anomaly_detection.py
```

## Dependencies

Add to `requirements.txt`:
```
numpy>=1.24.0
scikit-learn>=1.3.0
scipy>=1.11.0
```

## Best Practices

1. **Training Data**: Use at least 200-500 samples for initial training
2. **Incremental Updates**: Use `partial_fit()` for streaming data
3. **Model Versioning**: Save models after significant training sessions
4. **Threshold Tuning**: Adjust contamination and thresholds based on your data
5. **Feature Monitoring**: Track which features contribute most to anomalies
6. **Regular Retraining**: Periodically retrain with fresh data to adapt to drift

## Troubleshooting

### Model not fitting
- Ensure minimum samples (50+) for training
- Check for NaN values in data
- Verify feature extraction is working

### Too many false positives
- Reduce `contamination` parameter
- Increase anomaly thresholds
- Add more training data

### Too few detections
- Increase `contamination` parameter
- Lower anomaly thresholds
- Check feature quality

### Memory issues
- Reduce `n_estimators`
- Limit anomaly history size
- Use incremental learning instead of full retraining

## Future Enhancements

- [ ] Support for additional algorithms (LOF, Autoencoders)
- [ ] Multi-variate anomaly detection
- [ ] Automated threshold tuning
- [ ] Anomaly explanation with SHAP values
- [ ] Real-time streaming integration
- [ ] Anomaly clustering and pattern recognition
