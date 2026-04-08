"""
ML Module for PilotSuite Styx Core

Provides time series forecasting with LSTM and Transformer models.

Modules:
- lstm_forecast: LSTM-based forecasting for temperature and short-term predictions
- transformer_model: Transformer-based forecasting for energy and long sequences
- training_pipeline: Resumable training with checkpoints and experiment tracking

Usage:
    from copilot_core.ml import LSTMForecastManager, TransformerForecastManager
    from copilot_core.ml.training_pipeline import TrainingPipeline
"""

from .lstm_forecast import LSTMForecastManager, LSTMForecaster, forecast_temperature
from .transformer_model import TransformerForecastManager, TransformerForecaster
from .training_pipeline import TrainingPipeline, TrainingConfig, ExperimentTracker

__all__ = [
    "LSTMForecastManager",
    "LSTMForecaster",
    "forecast_temperature",
    "TransformerForecastManager",
    "TransformerForecaster",
    "TrainingPipeline",
    "TrainingConfig",
    "ExperimentTracker"
]
