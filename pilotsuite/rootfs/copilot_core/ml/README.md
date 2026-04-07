# ML Forecasting Module

Advanced machine learning module for time series forecasting in PilotSuite Styx Core.

## Features

### LSTM Forecasting (`lstm_forecast.py`)
- **Multi-horizon forecasting**: 1h, 6h, 24h, 7d predictions
- **Temperature-focused**: Optimized for sensor temperature data
- **Uncertainty estimation**: Monte Carlo dropout for confidence intervals
- **Model versioning**: Automatic versioning with checkpoint support

### Transformer Model (`transformer_model.py`)
- **Long-range dependencies**: Self-attention for complex temporal patterns
- **Energy forecasting**: Optimized for energy consumption prediction
- **Extended horizons**: Support for 24h, 48h, 7d, 30d forecasts
- **A/B testing**: Built-in model comparison framework

### Training Pipeline (`training_pipeline.py`)
- **Resumable training**: Checkpoint-based training that can resume from interruptions
- **Experiment tracking**: Full metrics logging and experiment management
- **Early stopping**: Automatic training termination on validation plateau
- **Model cleanup**: Automatic old checkpoint management

## API Endpoints

All endpoints are available under `/api/v1/ml/`

### Forecasting
- `POST /ml/lstm/models/<name>/predict` - LSTM prediction with uncertainty
- `POST /ml/transformer/models/<name>/predict` - Transformer prediction
- `POST /ml/forecast/temperature` - Quick temperature forecast

### Model Management
- `GET /ml/lstm/models` - List LSTM models
- `POST /ml/lstm/models` - Create LSTM model
- `POST /ml/lstm/models/<name>/train` - Train LSTM model
- `DELETE /ml/lstm/models/<name>` - Delete LSTM model

- `GET /ml/transformer/models` - List transformer models
- `POST /ml/transformer/models` - Create transformer model
- `POST /ml/transformer/models/<name>/train` - Train transformer model

### A/B Testing
- `GET /ml/ab-tests` - List A/B tests
- `POST /ml/ab-tests` - Create A/B test
- `POST /ml/ab-tests/<name>/predict` - Predict with A/B routing

### Training Pipeline
- `GET /ml/experiments` - List experiments
- `GET /ml/experiments/<id>` - Get experiment details
- `GET /ml/checkpoints` - List available checkpoints

## Usage Examples

### Python API

```python
from copilot_core.ml import LSTMForecastManager, TransformerForecastManager
import numpy as np

# LSTM for temperature forecasting
lstm = LSTMForecastManager()

# Create model
model_name = lstm.create_model(
    horizon="24h",
    hidden_size=64,
    num_layers=2
)

# Train
train_data = np.random.randn(1000, 1)  # Replace with real data
val_data = np.random.randn(200, 1)

results = lstm.train_model(
    model_name=model_name,
    train_data=train_data,
    val_data=val_data,
    epochs=50
)

# Predict
input_seq = train_data[-48:]  # Last 48 time steps
prediction = lstm.predict(
    model_name=model_name,
    input_sequence=input_seq,
    with_uncertainty=True
)

print(f"Forecast: {prediction['predictions']}")
```

### Transformer for Energy

```python
from copilot_core.ml import TransformerForecastManager

transformer = TransformerForecastManager()

# Create model for long-term energy forecast
model_name = transformer.create_model(
    horizon="7d",
    d_model=128,
    nhead=8,
    num_encoder_layers=4
)

# Setup A/B test
transformer.setup_ab_test(
    test_name="energy_v1_v2",
    model_a=f"transformer_7d_v1",
    model_b=f"transformer_7d_v2",
    traffic_split=0.5
)
```

### Training Pipeline

```python
from copilot_core.ml.training_pipeline import TrainingPipeline

pipeline = TrainingPipeline()

# Create config
config = pipeline.create_training_config(
    model_name="lstm_temp_24h",
    model_type="lstm",
    epochs=100,
    early_stopping_patience=15
)

# Start experiment
exp_id = pipeline.start_experiment(config, description="Temperature forecasting v1")

# Train with checkpoints
results = pipeline.train(
    experiment_id=exp_id,
    model=model,
    train_loader=train_loader,
    val_loader=val_loader
)

# Resume from checkpoint if needed
# pipeline.train(..., resume_from="checkpoints/ckpt_*.pt")
```

### REST API

```bash
# Create LSTM model
curl -X POST http://localhost:8080/api/v1/ml/lstm/models \
  -H "Content-Type: application/json" \
  -d '{"horizon": "24h", "hidden_size": 64}'

# Train model
curl -X POST http://localhost:8080/api/v1/ml/lstm/models/lstm_24h_abc123/train \
  -H "Content-Type: application/json" \
  -d '{
    "train_data": [[20.5], [21.0], ...],
    "epochs": 50
  }'

# Get prediction
curl -X POST http://localhost:8080/api/v1/ml/lstm/models/lstm_24h_abc123/predict \
  -H "Content-Type: application/json" \
  -d '{
    "input_sequence": [[20.5], [21.0], ...],
    "with_uncertainty": true
  }'
```

## Model Configuration

### LSTM Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `horizon` | "1h" | Forecast horizon (1h, 6h, 24h, 7d) |
| `hidden_size` | 64 | LSTM hidden layer size |
| `num_layers` | 2 | Number of LSTM layers |
| `dropout` | 0.2 | Dropout rate |
| `bidirectional` | False | Use bidirectional LSTM |

### Transformer Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `horizon` | "24h" | Forecast horizon (24h, 48h, 7d, 30d) |
| `d_model` | 64 | Model dimension |
| `nhead` | 4 | Attention heads |
| `num_encoder_layers` | 3 | Encoder layers |
| `dim_feedforward` | 128 | Feedforward dimension |
| `dropout` | 0.1 | Dropout rate |

## Dependencies

```
torch>=2.0.0
numpy>=1.24.0
flask>=2.3.0
```

## File Structure

```
copilot_core/ml/
├── __init__.py           # Module exports
├── lstm_forecast.py      # LSTM models
├── transformer_model.py  # Transformer models
├── training_pipeline.py  # Training with checkpoints
└── models/               # Saved model checkpoints
    ├── lstm_*.pt
    └── transformer_*.pt
```

## Best Practices

1. **Data Preprocessing**: Normalize/scale input data before training
2. **Sequence Length**: Use at least 2x the forecast horizon for training
3. **Validation Split**: Keep 10-20% of data for validation
4. **Early Stopping**: Enable to prevent overfitting
5. **Checkpointing**: Save checkpoints every 10 epochs for long training
6. **Model Versioning**: Always version models for A/B testing

## Troubleshooting

### PyTorch not available
```
Warning: PyTorch not available - LSTM forecasting disabled
```
Install PyTorch: `pip install torch`

### Data too short
```
ValueError: Data too short: 100 samples, need at least 72
```
Increase input data or reduce sequence length/horizon

### CUDA out of memory
Reduce `batch_size` or `d_model` parameters
