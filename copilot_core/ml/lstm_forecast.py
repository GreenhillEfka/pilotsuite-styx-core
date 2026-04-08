"""
LSTM-based Time Series Forecasting for PilotSuite Styx Core

Provides LSTM models for temperature and other sensor forecasting
with support for multiple forecast horizons (1h, 6h, 24h, 7d).

Features:
- Multi-horizon forecasting (1h, 6h, 24h, 7d)
- Confidence interval estimation via Monte Carlo dropout
- Model versioning and persistence
- Temperature-focused with extensible architecture
"""

from __future__ import annotations

import logging
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available - LSTM forecasting disabled")


class TimeSeriesDataset(Dataset):
    """Dataset for time series sequences."""
    
    def __init__(
        self,
        data: np.ndarray,
        seq_length: int,
        forecast_horizon: int = 1,
        target_col: int = 0
    ):
        """
        Initialize dataset.
        
        Args:
            data: 2D array of shape (time_steps, features)
            seq_length: Length of input sequences
            forecast_horizon: Number of steps to predict
            target_col: Column index for target variable
        """
        self.data = data
        self.seq_length = seq_length
        self.forecast_horizon = forecast_horizon
        self.target_col = target_col
        
        # Calculate valid indices
        self.valid_length = len(data) - seq_length - forecast_horizon + 1
        if self.valid_length <= 0:
            raise ValueError(
                f"Data too short: {len(data)} samples, need at least "
                f"{seq_length + forecast_horizon} for seq_length={seq_length}, "
                f"horizon={forecast_horizon}"
            )
    
    def __len__(self) -> int:
        return max(0, self.valid_length)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")
        
        x_start = idx
        x_end = idx + self.seq_length
        y_start = x_end
        y_end = y_start + self.forecast_horizon
        
        x = self.data[x_start:x_end, :]
        y = self.data[y_start:y_end, self.target_col]
        
        return (
            torch.FloatTensor(x),
            torch.FloatTensor(y)
        )


class LSTMForecaster(nn.Module):
    """LSTM model for time series forecasting."""
    
    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        forecast_horizon: int = 1,
        dropout: float = 0.2,
        bidirectional: bool = False
    ):
        """
        Initialize LSTM forecaster.
        
        Args:
            input_size: Number of input features
            hidden_size: LSTM hidden layer size
            num_layers: Number of LSTM layers
            forecast_horizon: Number of steps to predict
            dropout: Dropout rate for regularization
            bidirectional: Use bidirectional LSTM
        """
        super().__init__()
        
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.forecast_horizon = forecast_horizon
        self.dropout_rate = dropout
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_size * (2 if bidirectional else 1), hidden_size // 2)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size // 2, forecast_horizon)
    
    def forward(self, x: torch.Tensor, training: bool = False) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features)
            training: If True, apply dropout for MC dropout uncertainty
        
        Returns:
            Forecast tensor of shape (batch, forecast_horizon)
        """
        lstm_out, _ = self.lstm(x)
        
        # Take last time step
        last_output = lstm_out[:, -1, :]
        
        # Fully connected layers with dropout
        out = self.dropout(last_output) if training else self.dropout.eval()(last_output)
        out = self.fc1(out)
        out = self.relu(out)
        out = self.fc2(out)
        
        return out
    
    def predict_with_uncertainty(
        self,
        x: torch.Tensor,
        n_samples: int = 100,
        confidence_level: float = 0.95
    ) -> Dict[str, np.ndarray]:
        """
        Predict with uncertainty estimation via Monte Carlo dropout.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features) or (seq_len, features)
            n_samples: Number of Monte Carlo samples
            confidence_level: Confidence level for intervals (e.g., 0.95 for 95%)
        
        Returns:
            Dictionary with mean, std, lower_bound, upper_bound predictions
        """
        self.train()  # Enable dropout for MC sampling
        
        if x.dim() == 2:
            x = x.unsqueeze(0)  # Add batch dimension
        
        predictions = []
        with torch.no_grad():
            for _ in range(n_samples):
                pred = self.forward(x, training=True)
                predictions.append(pred.numpy())
        
        self.eval()
        
        predictions = np.vstack(predictions)  # (n_samples, batch, horizon)
        mean = np.mean(predictions, axis=0)
        std = np.std(predictions, axis=0)
        
        # Calculate confidence intervals
        z_score = {
            0.90: 1.645,
            0.95: 1.96,
            0.99: 2.576
        }.get(confidence_level, 1.96)
        
        lower_bound = mean - z_score * std
        upper_bound = mean + z_score * std
        
        return {
            "mean": mean.squeeze(),
            "std": std.squeeze(),
            "lower_bound": lower_bound.squeeze(),
            "upper_bound": upper_bound.squeeze(),
            "predictions": predictions.squeeze()
        }


class LSTMForecastManager:
    """Manager for LSTM forecasting models."""
    
    # Forecast horizons in hours
    HORIZONS = {
        "1h": 1,
        "6h": 6,
        "24h": 24,
        "7d": 168
    }
    
    def __init__(
        self,
        model_dir: Optional[str] = None,
        default_seq_length: int = 48,
        default_features: int = 1
    ):
        """
        Initialize forecast manager.
        
        Args:
            model_dir: Directory for model checkpoints
            default_seq_length: Default sequence length for training
            default_features: Default number of input features
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available - LSTM forecasting disabled")
        
        self.model_dir = Path(model_dir) if model_dir else Path(__file__).parent / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.default_seq_length = default_seq_length
        self.default_features = default_features
        
        self.models: Dict[str, LSTMForecaster] = {}
        self.model_metadata: Dict[str, Dict] = {}
        
        self._load_existing_models()
    
    def _generate_model_id(
        self,
        horizon: str,
        seq_length: int,
        hidden_size: int,
        num_layers: int
    ) -> str:
        """Generate unique model ID based on parameters."""
        params = f"{horizon}_{seq_length}_{hidden_size}_{num_layers}"
        return hashlib.md5(params.encode()).hexdigest()[:12]
    
    def _load_existing_models(self):
        """Load existing models from model directory."""
        if not self.model_dir.exists():
            return
        
        for model_file in self.model_dir.glob("lstm_*.pt"):
            try:
                model_name = model_file.stem
                self.load_model(model_name)
                logger.info(f"Loaded existing model: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to load model {model_file.name}: {e}")
    
    def create_model(
        self,
        horizon: str = "1h",
        hidden_size: int = 64,
        num_layers: int = 2,
        seq_length: Optional[int] = None,
        input_features: Optional[int] = None,
        dropout: float = 0.2,
        bidirectional: bool = False
    ) -> str:
        """
        Create a new LSTM model.
        
        Args:
            horizon: Forecast horizon ("1h", "6h", "24h", "7d")
            hidden_size: LSTM hidden layer size
            num_layers: Number of LSTM layers
            seq_length: Sequence length for training
            input_features: Number of input features
            dropout: Dropout rate
            bidirectional: Use bidirectional LSTM
        
        Returns:
            Model name/ID
        """
        if horizon not in self.HORIZONS:
            raise ValueError(f"Invalid horizon: {horizon}. Valid: {list(self.HORIZONS.keys())}")
        
        seq_length = seq_length or self.default_seq_length
        input_features = input_features or self.default_features
        
        model_id = self._generate_model_id(horizon, seq_length, hidden_size, num_layers)
        model_name = f"lstm_{horizon}_{model_id}"
        
        forecast_steps = self.HORIZONS[horizon]
        
        model = LSTMForecaster(
            input_size=input_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            forecast_horizon=forecast_steps,
            dropout=dropout,
            bidirectional=bidirectional
        )
        
        self.models[model_name] = model
        self.model_metadata[model_name] = {
            "horizon": horizon,
            "forecast_steps": forecast_steps,
            "seq_length": seq_length,
            "input_features": input_features,
            "hidden_size": hidden_size,
            "num_layers": num_layers,
            "dropout": dropout,
            "bidirectional": bidirectional,
            "created_at": datetime.now().isoformat(),
            "trained": False,
            "version": 1
        }
        
        logger.info(f"Created LSTM model: {model_name}")
        return model_name
    
    def train_model(
        self,
        model_name: str,
        train_data: np.ndarray,
        val_data: Optional[np.ndarray] = None,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        early_stopping_patience: int = 10,
        save_checkpoint: bool = True
    ) -> Dict[str, Any]:
        """
        Train an LSTM model.
        
        Args:
            model_name: Name of model to train
            train_data: Training data array (time_steps, features)
            val_data: Optional validation data
            epochs: Number of training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            early_stopping_patience: Patience for early stopping
            save_checkpoint: Whether to save model after training
        
        Returns:
            Training history and metrics
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        model = self.models[model_name]
        metadata = self.model_metadata[model_name]
        
        # Create datasets
        train_dataset = TimeSeriesDataset(
            train_data,
            seq_length=metadata["seq_length"],
            forecast_horizon=metadata["forecast_steps"]
        )
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            drop_last=True
        )
        
        val_loader = None
        if val_data is not None:
            val_dataset = TimeSeriesDataset(
                val_data,
                seq_length=metadata["seq_length"],
                forecast_horizon=metadata["forecast_steps"]
            )
            val_loader = DataLoader(
                val_dataset,
                batch_size=batch_size,
                shuffle=False
            )
        
        # Training setup
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )
        
        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        history = {
            "train_loss": [],
            "val_loss": [],
            "learning_rate": []
        }
        
        logger.info(f"Training model {model_name} on {device}")
        
        for epoch in range(epochs):
            # Training
            model.train()
            train_loss = 0.0
            for batch_x, batch_y in train_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                
                optimizer.zero_grad()
                output = model(batch_x)
                loss = criterion(output, batch_y)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
            
            train_loss /= len(train_loader)
            history["train_loss"].append(train_loss)
            history["learning_rate"].append(optimizer.param_groups[0]['lr'])
            
            # Validation
            val_loss = None
            if val_loader is not None:
                model.eval()
                val_loss = 0.0
                with torch.no_grad():
                    for batch_x, batch_y in val_loader:
                        batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                        output = model(batch_x)
                        loss = criterion(output, batch_y)
                        val_loss += loss.item()
                
                val_loss /= len(val_loader)
                history["val_loss"].append(val_loss)
                scheduler.step(val_loss)
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                
                if patience_counter >= early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break
            
            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch + 1}/{epochs} - "
                    f"train_loss: {train_loss:.6f}"
                    f"{f', val_loss: {val_loss:.6f}' if val_loss else ''}"
                )
        
        model.eval()
        metadata["trained"] = True
        metadata["trained_at"] = datetime.now().isoformat()
        metadata["epochs_trained"] = epoch + 1
        metadata["final_train_loss"] = train_loss
        metadata["final_val_loss"] = best_val_loss if best_val_loss != float('inf') else None
        
        # Save model
        if save_checkpoint:
            self.save_model(model_name)
        
        return {
            "model_name": model_name,
            "epochs_trained": epoch + 1,
            "final_train_loss": train_loss,
            "final_val_loss": best_val_loss if best_val_loss != float('inf') else None,
            "history": history
        }
    
    def predict(
        self,
        model_name: str,
        input_sequence: np.ndarray,
        with_uncertainty: bool = True,
        n_samples: int = 100,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Make predictions with a trained model.
        
        Args:
            model_name: Name of model to use
            input_sequence: Input sequence (seq_length, features)
            with_uncertainty: Whether to calculate uncertainty intervals
            n_samples: Number of MC samples for uncertainty
            confidence_level: Confidence level for intervals
        
        Returns:
            Prediction with optional uncertainty bounds
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        model = self.models[model_name]
        metadata = self.model_metadata[model_name]
        
        if not metadata.get("trained", False):
            raise ValueError(f"Model {model_name} is not trained")
        
        # Prepare input
        if input_sequence.ndim == 1:
            input_sequence = input_sequence.reshape(-1, 1)
        
        input_tensor = torch.FloatTensor(input_sequence).unsqueeze(0)
        
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        input_tensor = input_tensor.to(device)
        
        model.eval()
        
        if with_uncertainty:
            result = model.predict_with_uncertainty(
                input_tensor,
                n_samples=n_samples,
                confidence_level=confidence_level
            )
        else:
            with torch.no_grad():
                prediction = model(input_tensor)
            result = {
                "mean": prediction.cpu().numpy().squeeze(),
                "std": None,
                "lower_bound": None,
                "upper_bound": None
            }
        
        # Convert to time-indexed predictions
        forecast_steps = metadata["forecast_steps"]
        horizon = metadata["horizon"]
        
        predictions = []
        for i in range(forecast_steps):
            pred_data = {
                "step": i + 1,
                "time_offset": f"{(i + 1)}h",
                "value": float(result["mean"][i]) if forecast_steps > 1 else float(result["mean"]),
            }
            
            if with_uncertainty and result["std"] is not None:
                pred_data["std"] = float(result["std"][i]) if forecast_steps > 1 else float(result["std"])
                pred_data["lower_bound"] = float(result["lower_bound"][i]) if forecast_steps > 1 else float(result["lower_bound"])
                pred_data["upper_bound"] = float(result["upper_bound"][i]) if forecast_steps > 1 else float(result["upper_bound"])
                pred_data["confidence_level"] = confidence_level
            
            predictions.append(pred_data)
        
        return {
            "model_name": model_name,
            "horizon": horizon,
            "forecast_steps": forecast_steps,
            "predictions": predictions,
            "input_shape": list(input_sequence.shape),
            "timestamp": datetime.now().isoformat()
        }
    
    def save_model(self, model_name: str, version: Optional[int] = None):
        """
        Save model to disk.
        
        Args:
            model_name: Name of model to save
            version: Optional version number (auto-increments if not provided)
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        model = self.models[model_name]
        metadata = self.model_metadata[model_name]
        
        if version is None:
            version = metadata.get("version", 1)
        
        model_path = self.model_dir / f"{model_name}_v{version}.pt"
        metadata_path = self.model_dir / f"{model_name}_v{version}.json"
        
        # Save model weights
        torch.save({
            "model_state_dict": model.state_dict(),
            "metadata": metadata
        }, model_path)
        
        # Save metadata
        metadata["version"] = version
        metadata["model_path"] = str(model_path)
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update current version symlink
        current_path = self.model_dir / f"{model_name}.pt"
        if current_path.exists():
            current_path.unlink()
        current_path.symlink_to(f"{model_name}_v{version}.pt")
        
        logger.info(f"Saved model {model_name} version {version} to {model_path}")
    
    def load_model(self, model_name: str, version: Optional[int] = None) -> str:
        """
        Load model from disk.
        
        Args:
            model_name: Name of model to load
            version: Version to load (None for latest)
        
        Returns:
            Loaded model name
        """
        if version is None:
            # Find latest version
            model_files = list(self.model_dir.glob(f"{model_name}_v*.pt"))
            if not model_files:
                raise ValueError(f"No saved model found for {model_name}")
            
            versions = []
            for f in model_files:
                try:
                    v = int(f.stem.split('_v')[-1])
                    versions.append(v)
                except ValueError:
                    continue
            
            if not versions:
                raise ValueError(f"No valid model versions found for {model_name}")
            
            version = max(versions)
        
        model_path = self.model_dir / f"{model_name}_v{version}.pt"
        metadata_path = self.model_dir / f"{model_name}_v{version}.json"
        
        if not model_path.exists():
            raise ValueError(f"Model file not found: {model_path}")
        
        # Load checkpoint
        checkpoint = torch.load(model_path, map_location="cpu")
        
        # Recreate model from metadata
        metadata = checkpoint.get("metadata", {})
        if not metadata:
            # Try loading from JSON
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
        
        model = LSTMForecaster(
            input_size=metadata.get("input_features", 1),
            hidden_size=metadata.get("hidden_size", 64),
            num_layers=metadata.get("num_layers", 2),
            forecast_horizon=metadata.get("forecast_steps", 1),
            dropout=metadata.get("dropout", 0.2),
            bidirectional=metadata.get("bidirectional", False)
        )
        
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        
        self.models[model_name] = model
        self.model_metadata[model_name] = metadata
        
        logger.info(f"Loaded model {model_name} version {version}")
        return model_name
    
    def list_models(self) -> List[Dict]:
        """List all available models with metadata."""
        return [
            {
                "name": name,
                **metadata
            }
            for name, metadata in self.model_metadata.items()
        ]
    
    def delete_model(self, model_name: str, delete_all_versions: bool = False):
        """
        Delete model from memory and optionally from disk.
        
        Args:
            model_name: Name of model to delete
            delete_all_versions: If True, delete all versions from disk
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        # Remove from memory
        del self.models[model_name]
        del self.model_metadata[model_name]
        
        # Remove from disk if requested
        if delete_all_versions:
            for model_file in self.model_dir.glob(f"{model_name}*"):
                model_file.unlink()
            logger.info(f"Deleted all versions of model {model_name}")
        else:
            logger.info(f"Removed model {model_name} from memory")


# Convenience function for quick forecasting
def forecast_temperature(
    temperature_history: np.ndarray,
    horizon: str = "1h",
    model_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick temperature forecasting function.
    
    Args:
        temperature_history: Historical temperature data (1D array)
        horizon: Forecast horizon ("1h", "6h", "24h", "7d")
        model_dir: Directory for model storage
    
    Returns:
        Forecast predictions with confidence intervals
    """
    if not TORCH_AVAILABLE:
        return {"error": "PyTorch not available"}
    
    # Reshape to 2D
    if temperature_history.ndim == 1:
        temperature_history = temperature_history.reshape(-1, 1)
    
    manager = LSTMForecastManager(model_dir=model_dir)
    
    # Check for existing model or create new one
    model_name = f"lstm_{horizon}_temperature"
    if model_name not in manager.models:
        try:
            manager.load_model(model_name)
        except ValueError:
            # Create and train new model
            model_name = manager.create_model(
                horizon=horizon,
                hidden_size=32,
                num_layers=2,
                input_features=1
            )
            
            # Split data for training
            split_idx = int(len(temperature_history) * 0.8)
            train_data = temperature_history[:split_idx]
            val_data = temperature_history[split_idx:]
            
            manager.train_model(
                model_name=model_name,
                train_data=train_data,
                val_data=val_data,
                epochs=30,
                batch_size=16
            )
    
    # Make prediction
    return manager.predict(
        model_name=model_name,
        input_sequence=temperature_history[-48:]  # Last 48 time steps
    )
