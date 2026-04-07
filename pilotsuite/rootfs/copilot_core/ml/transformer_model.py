"""
Transformer-based Time Series Model for Long Sequence Forecasting

Optimized for energy consumption and other long-range dependency forecasting
with attention mechanisms for capturing complex temporal patterns.

Features:
- Self-attention for long-range dependencies
- Positional encoding for temporal awareness
- Multi-head attention for pattern diversity
- Suitable for energy consumption forecasting
- Model versioning and A/B testing support
"""

from __future__ import annotations

import logging
import os
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

# Stub classes for when torch is not available
class _StubDataset:
    pass

class _StubDataLoader:
    pass

class _StubNN:
    Module = object
    LSTM = object
    Linear = object
    Dropout = object
    MSELoss = object
    TransformerEncoder = object
    TransformerEncoderLayer = object
    MultiheadAttention = object
    LayerNorm = object

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available - Transformer modeling disabled")
    nn = _StubNN
    Dataset = _StubDataset
    DataLoader = _StubDataLoader


class PositionalEncoding(nn.Module):
    """Positional encoding for transformer models."""
    
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        """
        Initialize positional encoding.
        
        Args:
            d_model: Model dimension
            max_len: Maximum sequence length
            dropout: Dropout rate
        """
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model)
        )
        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Add positional encoding to input.
        
        Args:
            x: Input tensor (seq_len, batch, features)
        
        Returns:
            Encoded tensor
        """
        x = x + self.pe[:x.size(0)]
        return self.dropout(x)


class TransformerForecaster(nn.Module):
    """Transformer model for time series forecasting."""
    
    def __init__(
        self,
        input_size: int = 1,
        d_model: int = 64,
        nhead: int = 4,
        num_encoder_layers: int = 3,
        dim_feedforward: int = 128,
        forecast_horizon: int = 24,
        seq_length: int = 96,
        dropout: float = 0.1,
        activation: str = "relu"
    ):
        """
        Initialize transformer forecaster.
        
        Args:
            input_size: Number of input features
            d_model: Transformer model dimension
            nhead: Number of attention heads
            num_encoder_layers: Number of encoder layers
            dim_feedforward: Feedforward dimension
            forecast_horizon: Number of steps to predict
            seq_length: Input sequence length
            dropout: Dropout rate
            activation: Activation function ("relu" or "gelu")
        """
        super().__init__()
        
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")
        
        self.input_size = input_size
        self.d_model = d_model
        self.nhead = nhead
        self.forecast_horizon = forecast_horizon
        self.seq_length = seq_length
        
        # Input embedding
        self.input_embedding = nn.Linear(input_size, d_model)
        
        # Positional encoding
        self.pos_encoder = PositionalEncoding(d_model, dropout=dropout)
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation=activation,
            batch_first=False
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_encoder_layers
        )
        
        # Output projection
        self.fc1 = nn.Linear(d_model, d_model // 2)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(d_model // 2, forecast_horizon)
        
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights with Xavier uniform."""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)
    
    def generate_square_subsequent_mask(self, sz: int) -> torch.Tensor:
        """Generate causal mask for attention."""
        mask = torch.triu(torch.ones(sz, sz), diagonal=1)
        mask = mask.masked_fill(mask == 1, float('-inf'))
        return mask
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor (batch, seq_len, features)
        
        Returns:
            Forecast tensor (batch, forecast_horizon)
        """
        # Embed input
        x = self.input_embedding(x) * math.sqrt(self.d_model)
        
        # Transpose for transformer (seq_len, batch, d_model)
        x = x.transpose(0, 1)
        
        # Add positional encoding
        x = self.pos_encoder(x)
        
        # Transformer encoding
        x = self.transformer_encoder(x)
        
        # Take mean over sequence (global pooling)
        x = x.mean(dim=0)
        
        # Output layers
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        
        return x
    
    def predict_with_attention(
        self,
        x: torch.Tensor,
        return_attention: bool = False
    ) -> Dict[str, Any]:
        """
        Predict with attention weight visualization.
        
        Args:
            x: Input tensor (batch, seq_len, features)
            return_attention: Whether to return attention weights
        
        Returns:
            Prediction with optional attention weights
        """
        self.eval()
        
        # Embed and encode
        x_emb = self.input_embedding(x) * math.sqrt(self.d_model)
        x_emb = x_emb.transpose(0, 1)
        x_emb = self.pos_encoder(x_emb)
        
        # Get attention weights from each layer
        attention_weights = []
        
        if return_attention:
            with torch.no_grad():
                for i, layer in enumerate(self.transformer_encoder.layers):
                    x_emb = layer.norm1(x_emb + layer._sa_block(x_emb, None, None))
                    x_emb = layer.norm2(x_emb + layer.ffn(x_emb))
                    
                    # Extract attention (simplified)
                    # Note: PyTorch doesn't expose attention directly in encoder
                    # This is a placeholder for attention extraction
        else:
            with torch.no_grad():
                x_emb = self.transformer_encoder(x_emb)
        
        # Pool and project
        x_pool = x_emb.mean(dim=0)
        prediction = self.fc2(self.relu(self.dropout(self.fc1(x_pool))))
        
        result = {
            "prediction": prediction.cpu().numpy().squeeze(),
        }
        
        if return_attention and attention_weights:
            result["attention_weights"] = [aw.cpu().numpy() for aw in attention_weights]
        
        return result


class TransformerForecastManager:
    """Manager for transformer forecasting models."""
    
    # Common forecast horizons for energy
    HORIZONS = {
        "1h": 1,
        "6h": 6,
        "24h": 24,
        "48h": 48,
        "7d": 168,
        "30d": 720
    }
    
    def __init__(
        self,
        model_dir: Optional[str] = None,
        default_seq_length: int = 96,
        default_features: int = 1
    ):
        """
        Initialize transformer manager.
        
        Args:
            model_dir: Directory for model checkpoints
            default_seq_length: Default sequence length
            default_features: Default number of features
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")
        
        self.model_dir = Path(model_dir) if model_dir else Path(__file__).parent / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.default_seq_length = default_seq_length
        self.default_features = default_features
        
        self.models: Dict[str, TransformerForecaster] = {}
        self.model_metadata: Dict[str, Dict] = {}
        self.ab_tests: Dict[str, Dict] = {}
        
        self._load_existing_models()
    
    def _generate_model_id(
        self,
        horizon: str,
        d_model: int,
        nhead: int,
        num_layers: int
    ) -> str:
        """Generate unique model ID."""
        import hashlib
        params = f"{horizon}_{d_model}_{nhead}_{num_layers}"
        return hashlib.md5(params.encode()).hexdigest()[:12]
    
    def _load_existing_models(self):
        """Load existing models from disk."""
        if not self.model_dir.exists():
            return
        
        for model_file in self.model_dir.glob("transformer_*.pt"):
            try:
                model_name = model_file.stem.split('_v')[0]
                self.load_model(model_name)
                logger.info(f"Loaded transformer model: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to load {model_file.name}: {e}")
    
    def create_model(
        self,
        horizon: str = "24h",
        d_model: int = 64,
        nhead: int = 4,
        num_encoder_layers: int = 3,
        dim_feedforward: int = 128,
        seq_length: Optional[int] = None,
        input_features: Optional[int] = None,
        dropout: float = 0.1,
        activation: str = "relu",
        model_name: Optional[str] = None
    ) -> str:
        """
        Create a new transformer model.
        
        Args:
            horizon: Forecast horizon
            d_model: Model dimension
            nhead: Number of attention heads
            num_encoder_layers: Number of encoder layers
            dim_feedforward: Feedforward dimension
            seq_length: Sequence length
            input_features: Number of input features
            dropout: Dropout rate
            activation: Activation function
            model_name: Custom model name
        
        Returns:
            Model name
        """
        if horizon not in self.HORIZONS:
            raise ValueError(f"Invalid horizon: {horizon}. Valid: {list(self.HORIZONS.keys())}")
        
        seq_length = seq_length or self.default_seq_length
        input_features = input_features or self.default_features
        
        if model_name is None:
            model_id = self._generate_model_id(horizon, d_model, nhead, num_encoder_layers)
            model_name = f"transformer_{horizon}_{model_id}"
        
        forecast_steps = self.HORIZONS[horizon]
        
        model = TransformerForecaster(
            input_size=input_features,
            d_model=d_model,
            nhead=nhead,
            num_encoder_layers=num_encoder_layers,
            dim_feedforward=dim_feedforward,
            forecast_horizon=forecast_steps,
            seq_length=seq_length,
            dropout=dropout,
            activation=activation
        )
        
        self.models[model_name] = model
        self.model_metadata[model_name] = {
            "horizon": horizon,
            "forecast_steps": forecast_steps,
            "seq_length": seq_length,
            "input_features": input_features,
            "d_model": d_model,
            "nhead": nhead,
            "num_encoder_layers": num_encoder_layers,
            "dim_feedforward": dim_feedforward,
            "dropout": dropout,
            "activation": activation,
            "created_at": datetime.now().isoformat(),
            "trained": False,
            "version": 1,
            "model_type": "transformer"
        }
        
        logger.info(f"Created transformer model: {model_name}")
        return model_name
    
    def train_model(
        self,
        model_name: str,
        train_data: np.ndarray,
        val_data: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.0005,
        early_stopping_patience: int = 15,
        save_checkpoint: bool = True,
        gradient_clip: float = 1.0
    ) -> Dict[str, Any]:
        """
        Train transformer model.
        
        Args:
            model_name: Model to train
            train_data: Training data (time_steps, features)
            val_data: Validation data
            epochs: Training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            early_stopping_patience: Early stopping patience
            save_checkpoint: Save after training
            gradient_clip: Gradient clipping value
        
        Returns:
            Training history
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        model = self.models[model_name]
        metadata = self.model_metadata[model_name]
        
        # Dataset
        class TransformerDataset(Dataset):
            def __init__(self, data, seq_len, horizon):
                self.data = data
                self.seq_len = seq_len
                self.horizon = horizon
                self.valid_len = len(data) - seq_len - horizon + 1
            
            def __len__(self):
                return max(0, self.valid_len)
            
            def __getitem__(self, idx):
                x = self.data[idx:idx + self.seq_len]
                y = self.data[idx + self.seq_len:idx + self.seq_len + self.horizon, 0]
                return torch.FloatTensor(x), torch.FloatTensor(y)
        
        train_dataset = TransformerDataset(
            train_data,
            metadata["seq_length"],
            metadata["forecast_steps"]
        )
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            drop_last=True
        )
        
        val_loader = None
        if val_data is not None:
            val_dataset = TransformerDataset(
                val_data,
                metadata["seq_length"],
                metadata["forecast_steps"]
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
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=epochs, eta_min=learning_rate / 10
        )
        
        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        history = {"train_loss": [], "val_loss": [], "learning_rate": []}
        
        logger.info(f"Training transformer {model_name} on {device}")
        
        for epoch in range(epochs):
            model.train()
            train_loss = 0.0
            
            for batch_x, batch_y in train_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                
                optimizer.zero_grad()
                output = model(batch_x)
                loss = criterion(output, batch_y)
                loss.backward()
                
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)
                
                optimizer.step()
                train_loss += loss.item()
            
            train_loss /= len(train_loader)
            history["train_loss"].append(train_loss)
            history["learning_rate"].append(scheduler.get_last_lr()[0])
            
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
                
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                
                if patience_counter >= early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break
            
            scheduler.step()
            
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
        return_attention: bool = False
    ) -> Dict[str, Any]:
        """
        Make predictions.
        
        Args:
            model_name: Model to use
            input_sequence: Input sequence (seq_len, features)
            return_attention: Return attention weights
        
        Returns:
            Predictions
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        model = self.models[model_name]
        metadata = self.model_metadata[model_name]
        
        if not metadata.get("trained", False):
            raise ValueError(f"Model {model_name} not trained")
        
        if input_sequence.ndim == 1:
            input_sequence = input_sequence.reshape(-1, 1)
        
        input_tensor = torch.FloatTensor(input_sequence).unsqueeze(0)
        
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        input_tensor = input_tensor.to(device)
        
        model.eval()
        
        with torch.no_grad():
            prediction = model(input_tensor)
        
        forecast_steps = metadata["forecast_steps"]
        pred_values = prediction.cpu().numpy().squeeze()
        
        predictions = []
        for i in range(forecast_steps):
            predictions.append({
                "step": i + 1,
                "time_offset": f"{(i + 1)}h",
                "value": float(pred_values[i]) if forecast_steps > 1 else float(pred_values)
            })
        
        result = {
            "model_name": model_name,
            "horizon": metadata["horizon"],
            "forecast_steps": forecast_steps,
            "predictions": predictions,
            "timestamp": datetime.now().isoformat()
        }
        
        if return_attention:
            result["attention_analysis"] = "Available via predict_with_attention method"
        
        return result
    
    def setup_ab_test(
        self,
        test_name: str,
        model_a: str,
        model_b: str,
        traffic_split: float = 0.5
    ):
        """
        Setup A/B test between two models.
        
        Args:
            test_name: Test identifier
            model_a: Model A name
            model_b: Model B name
            traffic_split: Traffic split for model A (0-1)
        """
        if model_a not in self.models or model_b not in self.models:
            raise ValueError("Both models must exist")
        
        self.ab_tests[test_name] = {
            "model_a": model_a,
            "model_b": model_b,
            "traffic_split": traffic_split,
            "created_at": datetime.now().isoformat(),
            "predictions_a": 0,
            "predictions_b": 0
        }
        
        logger.info(f"Setup A/B test '{test_name}': {model_a} vs {model_b}")
    
    def predict_ab_test(self, test_name: str, input_sequence: np.ndarray) -> Dict[str, Any]:
        """
        Make prediction using A/B test routing.
        
        Args:
            test_name: Test name
            input_sequence: Input sequence
        
        Returns:
            Prediction from selected model
        """
        if test_name not in self.ab_tests:
            raise ValueError(f"A/B test {test_name} not found")
        
        test = self.ab_tests[test_name]
        
        # Route based on traffic split
        if np.random.random() < test["traffic_split"]:
            model_name = test["model_a"]
            test["predictions_a"] += 1
        else:
            model_name = test["model_b"]
            test["predictions_b"] += 1
        
        return self.predict(model_name, input_sequence)
    
    def save_model(self, model_name: str, version: Optional[int] = None):
        """Save model to disk."""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        model = self.models[model_name]
        metadata = self.model_metadata[model_name]
        
        if version is None:
            version = metadata.get("version", 1)
        
        model_path = self.model_dir / f"{model_name}_v{version}.pt"
        
        torch.save({
            "model_state_dict": model.state_dict(),
            "metadata": metadata
        }, model_path)
        
        metadata["version"] = version
        metadata["model_path"] = str(model_path)
        
        # Save metadata JSON
        metadata_path = self.model_dir / f"{model_name}_v{version}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update symlink
        current_path = self.model_dir / f"{model_name}.pt"
        if current_path.exists():
            current_path.unlink()
        current_path.symlink_to(f"{model_name}_v{version}.pt")
        
        logger.info(f"Saved transformer {model_name} v{version}")
    
    def load_model(self, model_name: str, version: Optional[int] = None) -> str:
        """Load model from disk."""
        if version is None:
            model_files = list(self.model_dir.glob(f"{model_name}_v*.pt"))
            if not model_files:
                raise ValueError(f"No saved model: {model_name}")
            
            versions = [int(f.stem.split('_v')[-1]) for f in model_files if '_v' in f.stem]
            version = max(versions)
        
        model_path = self.model_dir / f"{model_name}_v{version}.pt"
        
        if not model_path.exists():
            raise ValueError(f"Model not found: {model_path}")
        
        checkpoint = torch.load(model_path, map_location="cpu")
        metadata = checkpoint.get("metadata", {})
        
        model = TransformerForecaster(
            input_size=metadata.get("input_features", 1),
            d_model=metadata.get("d_model", 64),
            nhead=metadata.get("nhead", 4),
            num_encoder_layers=metadata.get("num_encoder_layers", 3),
            forecast_horizon=metadata.get("forecast_steps", 24),
            seq_length=metadata.get("seq_length", 96)
        )
        
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        
        self.models[model_name] = model
        self.model_metadata[model_name] = metadata
        
        logger.info(f"Loaded transformer {model_name} v{version}")
        return model_name
    
    def list_models(self) -> List[Dict]:
        """List all models."""
        return [{"name": name, **meta} for name, meta in self.model_metadata.items()]
