"""
Training Pipeline for ML Models with Checkpoint Support

Provides resumable training pipelines for LSTM and Transformer models
with checkpoint management, experiment tracking, and distributed training support.

Features:
- Checkpoint-based training (resumable)
- Experiment tracking and metrics logging
- Model versioning
- Early stopping with patience
- Learning rate scheduling
- Multi-model training orchestration
"""

from __future__ import annotations

import logging
import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available - Training pipeline disabled")


@dataclass
class TrainingConfig:
    """Configuration for training pipeline."""
    model_name: str
    model_type: str  # "lstm" or "transformer"
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    early_stopping_patience: int = 15
    checkpoint_interval: int = 10
    save_best_only: bool = True
    gradient_clip: float = 1.0
    validation_split: float = 0.2
    shuffle: bool = True
    seed: int = 42
    device: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TrainingConfig':
        return cls(**data)


@dataclass
class Checkpoint:
    """Checkpoint metadata."""
    checkpoint_id: str
    model_name: str
    epoch: int
    train_loss: float
    val_loss: Optional[float]
    timestamp: str
    is_best: bool = False
    path: Optional[str] = None


class ExperimentTracker:
    """Track training experiments and metrics."""
    
    def __init__(self, experiment_dir: Optional[str] = None):
        """
        Initialize experiment tracker.
        
        Args:
            experiment_dir: Directory for experiment logs
        """
        self.experiment_dir = Path(experiment_dir) if experiment_dir else Path(__file__).parent / "experiments"
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        
        self.experiments: Dict[str, Dict] = {}
        self._load_experiments()
    
    def _load_experiments(self):
        """Load existing experiments."""
        for exp_file in self.experiment_dir.glob("experiment_*.json"):
            try:
                with open(exp_file, 'r') as f:
                    exp_data = json.load(f)
                    self.experiments[exp_data["experiment_id"]] = exp_data
            except Exception as e:
                logger.warning(f"Failed to load experiment {exp_file}: {e}")
    
    def create_experiment(
        self,
        model_name: str,
        config: TrainingConfig,
        description: str = ""
    ) -> str:
        """
        Create new experiment.
        
        Args:
            model_name: Model being trained
            config: Training configuration
            description: Experiment description
        
        Returns:
            Experiment ID
        """
        exp_id = f"exp_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        experiment = {
            "experiment_id": exp_id,
            "model_name": model_name,
            "model_type": config.model_type,
            "config": config.to_dict(),
            "description": description,
            "created_at": datetime.now().isoformat(),
            "status": "running",
            "epochs_completed": 0,
            "best_val_loss": None,
            "best_epoch": None,
            "metrics_history": {
                "train_loss": [],
                "val_loss": [],
                "learning_rate": []
            },
            "checkpoints": []
        }
        
        self.experiments[exp_id] = experiment
        self._save_experiment(exp_id)
        
        logger.info(f"Created experiment: {exp_id}")
        return exp_id
    
    def log_epoch(
        self,
        experiment_id: str,
        epoch: int,
        train_loss: float,
        val_loss: Optional[float] = None,
        learning_rate: Optional[float] = None
    ):
        """
        Log epoch metrics.
        
        Args:
            experiment_id: Experiment ID
            epoch: Epoch number
            train_loss: Training loss
            val_loss: Validation loss
            learning_rate: Current learning rate
        """
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        exp = self.experiments[experiment_id]
        exp["epochs_completed"] = epoch
        
        exp["metrics_history"]["train_loss"].append({
            "epoch": epoch,
            "value": train_loss
        })
        
        if val_loss is not None:
            exp["metrics_history"]["val_loss"].append({
                "epoch": epoch,
                "value": val_loss
            })
            
            # Track best
            if exp["best_val_loss"] is None or val_loss < exp["best_val_loss"]:
                exp["best_val_loss"] = val_loss
                exp["best_epoch"] = epoch
        
        if learning_rate is not None:
            exp["metrics_history"]["learning_rate"].append({
                "epoch": epoch,
                "value": learning_rate
            })
        
        self._save_experiment(experiment_id)
    
    def add_checkpoint(
        self,
        experiment_id: str,
        checkpoint: Checkpoint
    ):
        """Add checkpoint to experiment."""
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        exp = self.experiments[experiment_id]
        exp["checkpoints"].append({
            "checkpoint_id": checkpoint.checkpoint_id,
            "epoch": checkpoint.epoch,
            "train_loss": checkpoint.train_loss,
            "val_loss": checkpoint.val_loss,
            "is_best": checkpoint.is_best,
            "timestamp": checkpoint.timestamp,
            "path": checkpoint.path
        })
        
        self._save_experiment(experiment_id)
    
    def complete_experiment(
        self,
        experiment_id: str,
        status: str = "completed"
    ):
        """
        Mark experiment as complete.
        
        Args:
            experiment_id: Experiment ID
            status: Final status (completed, failed, stopped)
        """
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        exp = self.experiments[experiment_id]
        exp["status"] = status
        exp["completed_at"] = datetime.now().isoformat()
        
        self._save_experiment(experiment_id)
    
    def _save_experiment(self, experiment_id: str):
        """Save experiment to disk."""
        exp_path = self.experiment_dir / f"{experiment_id}.json"
        with open(exp_path, 'w') as f:
            json.dump(self.experiments[experiment_id], f, indent=2)
    
    def get_experiment(self, experiment_id: str) -> Dict:
        """Get experiment data."""
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")
        return self.experiments[experiment_id]
    
    def list_experiments(
        self,
        model_name: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        List experiments with optional filters.
        
        Args:
            model_name: Filter by model name
            status: Filter by status
        
        Returns:
            List of experiment summaries
        """
        results = []
        for exp_id, exp in self.experiments.items():
            if model_name and exp.get("model_name") != model_name:
                continue
            if status and exp.get("status") != status:
                continue
            results.append({
                "experiment_id": exp_id,
                "model_name": exp.get("model_name"),
                "status": exp.get("status"),
                "created_at": exp.get("created_at"),
                "best_val_loss": exp.get("best_val_loss"),
                "epochs_completed": exp.get("epochs_completed")
            })
        return results


class TrainingPipeline:
    """
    Training pipeline with checkpoint support.
    
    Provides resumable training for LSTM and Transformer models.
    """
    
    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        experiment_dir: Optional[str] = None
    ):
        """
        Initialize training pipeline.
        
        Args:
            checkpoint_dir: Directory for checkpoints
            experiment_dir: Directory for experiment logs
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")
        
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else Path(__file__).parent / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.tracker = ExperimentTracker(experiment_dir)
        
        self.active_experiments: Dict[str, Dict] = {}
        self._load_checkpoints()
    
    def _load_checkpoints(self):
        """Load existing checkpoints."""
        self.available_checkpoints: Dict[str, List[Checkpoint]] = {}
        
        for ckpt_file in self.checkpoint_dir.glob("*.pt"):
            try:
                checkpoint = torch.load(ckpt_file, map_location="cpu")
                metadata = checkpoint.get("metadata", {})
                
                model_name = metadata.get("model_name", "unknown")
                if model_name not in self.available_checkpoints:
                    self.available_checkpoints[model_name] = []
                
                ckpt = Checkpoint(
                    checkpoint_id=metadata.get("checkpoint_id", ckpt_file.stem),
                    model_name=model_name,
                    epoch=metadata.get("epoch", 0),
                    train_loss=metadata.get("train_loss", 0),
                    val_loss=metadata.get("val_loss"),
                    timestamp=metadata.get("timestamp", ""),
                    is_best=metadata.get("is_best", False),
                    path=str(ckpt_file)
                )
                self.available_checkpoints[model_name].append(ckpt)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {ckpt_file}: {e}")
    
    def create_training_config(
        self,
        model_name: str,
        model_type: str,
        **kwargs
    ) -> TrainingConfig:
        """
        Create training configuration.
        
        Args:
            model_name: Model name
            model_type: "lstm" or "transformer"
            **kwargs: Override default config values
        
        Returns:
            TrainingConfig instance
        """
        return TrainingConfig(
            model_name=model_name,
            model_type=model_type,
            **kwargs
        )
    
    def start_experiment(
        self,
        config: TrainingConfig,
        description: str = ""
    ) -> str:
        """
        Start new experiment.
        
        Args:
            config: Training configuration
            description: Experiment description
        
        Returns:
            Experiment ID
        """
        exp_id = self.tracker.create_experiment(
            model_name=config.model_name,
            config=config,
            description=description
        )
        
        self.active_experiments[exp_id] = {
            "config": config,
            "start_time": datetime.now()
        }
        
        return exp_id
    
    def train(
        self,
        experiment_id: str,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader] = None,
        resume_from: Optional[str] = None,
        callbacks: Optional[List[Callable]] = None
    ) -> Dict[str, Any]:
        """
        Train model with checkpoint support.
        
        Args:
            experiment_id: Experiment ID
            model: Model to train
            train_loader: Training data loader
            val_loader: Validation data loader
            resume_from: Checkpoint path to resume from
            callbacks: List of callback functions
        
        Returns:
            Training results
        """
        if experiment_id not in self.tracker.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        exp = self.tracker.get_experiment(experiment_id)
        config = TrainingConfig.from_dict(exp["config"])
        
        # Setup device
        if config.device:
            device = torch.device(config.device)
        else:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        model = model.to(device)
        
        # Loss and optimizer
        criterion = nn.MSELoss()
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=0.01
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )
        
        # Resume from checkpoint
        start_epoch = 0
        best_val_loss = float('inf')
        
        if resume_from and Path(resume_from).exists():
            logger.info(f"Resuming from checkpoint: {resume_from}")
            checkpoint = torch.load(resume_from, map_location="cpu")
            model.load_state_dict(checkpoint["model_state_dict"])
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            start_epoch = checkpoint.get("epoch", 0) + 1
            best_val_loss = checkpoint.get("val_loss", float('inf'))
            logger.info(f"Resumed from epoch {start_epoch}")
        
        # Training loop
        patience_counter = 0
        history = {"train_loss": [], "val_loss": [], "learning_rate": []}
        
        logger.info(f"Training {config.model_name} on {device}")
        
        for epoch in range(start_epoch, config.epochs):
            # Training
            model.train()
            train_loss = 0.0
            
            for batch_x, batch_y in train_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                
                optimizer.zero_grad()
                output = model(batch_x)
                loss = criterion(output, batch_y)
                loss.backward()
                
                # Gradient clipping
                if config.gradient_clip > 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip)
                
                optimizer.step()
                train_loss += loss.item()
            
            train_loss /= len(train_loader)
            lr = optimizer.param_groups[0]['lr']
            
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
                scheduler.step(val_loss)
                
                # Early stopping
                if config.save_best_only and val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    self._save_checkpoint(
                        experiment_id=experiment_id,
                        model=model,
                        optimizer=optimizer,
                        epoch=epoch,
                        train_loss=train_loss,
                        val_loss=val_loss,
                        is_best=True
                    )
                else:
                    patience_counter += 1
                
                if patience_counter >= config.early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break
            
            # Log metrics
            self.tracker.log_epoch(
                experiment_id=experiment_id,
                epoch=epoch + 1,
                train_loss=train_loss,
                val_loss=val_loss,
                learning_rate=lr
            )
            
            # Periodic checkpoint
            if (epoch + 1) % config.checkpoint_interval == 0:
                self._save_checkpoint(
                    experiment_id=experiment_id,
                    model=model,
                    optimizer=optimizer,
                    epoch=epoch,
                    train_loss=train_loss,
                    val_loss=val_loss,
                    is_best=False
                )
            
            # Callbacks
            if callbacks:
                for callback in callbacks:
                    callback(epoch, train_loss, val_loss, model)
            
            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch + 1}/{config.epochs} - "
                    f"train_loss: {train_loss:.6f}"
                    f"{f', val_loss: {val_loss:.6f}' if val_loss else ''}"
                )
        
        # Complete experiment
        status = "completed" if patience_counter < config.early_stopping_patience else "early_stopped"
        self.tracker.complete_experiment(experiment_id, status)
        
        # Final checkpoint
        self._save_checkpoint(
            experiment_id=experiment_id,
            model=model,
            optimizer=optimizer,
            epoch=epoch,
            train_loss=train_loss,
            val_loss=best_val_loss if best_val_loss != float('inf') else val_loss,
            is_best=True
        )
        
        return {
            "experiment_id": experiment_id,
            "model_name": config.model_name,
            "epochs_trained": epoch + 1,
            "final_train_loss": train_loss,
            "final_val_loss": best_val_loss if best_val_loss != float('inf') else val_loss,
            "status": status,
            "checkpoint_dir": str(self.checkpoint_dir)
        }
    
    def _save_checkpoint(
        self,
        experiment_id: str,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        epoch: int,
        train_loss: float,
        val_loss: Optional[float],
        is_best: bool = False
    ) -> str:
        """
        Save training checkpoint.
        
        Args:
            experiment_id: Experiment ID
            model: Model to save
            optimizer: Optimizer state
            epoch: Current epoch
            train_loss: Training loss
            val_loss: Validation loss
            is_best: Is this the best checkpoint
        
        Returns:
            Checkpoint path
        """
        exp = self.tracker.get_experiment(experiment_id)
        config = TrainingConfig.from_dict(exp["config"])
        
        checkpoint_id = f"ckpt_{config.model_name}_epoch{epoch}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.pt"
        
        torch.save({
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "train_loss": train_loss,
            "val_loss": val_loss,
            "is_best": is_best,
            "metadata": {
                "checkpoint_id": checkpoint_id,
                "experiment_id": experiment_id,
                "model_name": config.model_name,
                "model_type": config.model_type,
                "timestamp": datetime.now().isoformat()
            }
        }, checkpoint_path)
        
        # Track checkpoint
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            model_name=config.model_name,
            epoch=epoch,
            train_loss=train_loss,
            val_loss=val_loss,
            timestamp=datetime.now().isoformat(),
            is_best=is_best,
            path=str(checkpoint_path)
        )
        
        self.tracker.add_checkpoint(experiment_id, checkpoint)
        
        logger.info(f"Saved checkpoint: {checkpoint_path}")
        return str(checkpoint_path)
    
    def list_checkpoints(self, model_name: Optional[str] = None) -> List[Dict]:
        """
        List available checkpoints.
        
        Args:
            model_name: Filter by model name
        
        Returns:
            List of checkpoint metadata
        """
        self._load_checkpoints()
        
        if model_name:
            return [
                asdict(ckpt)
                for ckpt in self.available_checkpoints.get(model_name, [])
            ]
        
        all_checkpoints = []
        for ckpts in self.available_checkpoints.values():
            all_checkpoints.extend([asdict(c) for c in ckpts])
        
        return all_checkpoints
    
    def load_checkpoint(
        self,
        checkpoint_path: str,
        model: nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None
    ) -> Dict[str, Any]:
        """
        Load checkpoint for resuming training.
        
        Args:
            checkpoint_path: Path to checkpoint
            model: Model to load weights into
            optimizer: Optimizer to load state into
        
        Returns:
            Checkpoint metadata
        """
        if not Path(checkpoint_path).exists():
            raise ValueError(f"Checkpoint not found: {checkpoint_path}")
        
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
        
        model.load_state_dict(checkpoint["model_state_dict"])
        
        if optimizer is not None:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        
        metadata = checkpoint.get("metadata", {})
        
        logger.info(f"Loaded checkpoint from epoch {checkpoint.get('epoch', 0)}")
        
        return {
            "epoch": checkpoint.get("epoch", 0),
            "train_loss": checkpoint.get("train_loss"),
            "val_loss": checkpoint.get("val_loss"),
            "is_best": checkpoint.get("is_best", False),
            "metadata": metadata
        }
    
    def cleanup_old_checkpoints(
        self,
        model_name: str,
        keep_last: int = 3,
        keep_best: bool = True
    ):
        """
        Cleanup old checkpoints to save space.
        
        Args:
            model_name: Model to cleanup
            keep_last: Number of recent checkpoints to keep
            keep_best: Always keep best checkpoint
        """
        checkpoints = self.list_checkpoints(model_name)
        
        if len(checkpoints) <= keep_last:
            return
        
        # Sort by epoch
        checkpoints.sort(key=lambda x: x["epoch"], reverse=True)
        
        # Identify checkpoints to delete
        to_delete = []
        best_ckpt = None
        
        for i, ckpt in enumerate(checkpoints):
            if keep_best and ckpt.get("is_best"):
                best_ckpt = ckpt
                continue
            
            if i >= keep_last:
                to_delete.append(ckpt)
        
        # Delete
        for ckpt in to_delete:
            if ckpt["path"] and Path(ckpt["path"]).exists():
                Path(ckpt["path"]).unlink()
                logger.info(f"Deleted old checkpoint: {ckpt['path']}")
    
    def get_experiment_summary(self, experiment_id: str) -> Dict:
        """
        Get experiment summary.
        
        Args:
            experiment_id: Experiment ID
        
        Returns:
            Summary dictionary
        """
        exp = self.tracker.get_experiment(experiment_id)
        
        # Calculate summary statistics
        train_losses = [m["value"] for m in exp["metrics_history"]["train_loss"]]
        val_losses = [m["value"] for m in exp["metrics_history"]["val_loss"]]
        
        return {
            "experiment_id": experiment_id,
            "model_name": exp["model_name"],
            "status": exp["status"],
            "epochs_completed": exp["epochs_completed"],
            "best_val_loss": exp["best_val_loss"],
            "best_epoch": exp["best_epoch"],
            "final_train_loss": train_losses[-1] if train_losses else None,
            "final_val_loss": val_losses[-1] if val_losses else None,
            "num_checkpoints": len(exp["checkpoints"]),
            "created_at": exp["created_at"],
            "completed_at": exp.get("completed_at")
        }


# Convenience function for quick training
def train_model_quick(
    model: nn.Module,
    train_data: np.ndarray,
    val_data: Optional[np.ndarray] = None,
    model_name: str = "model",
    model_type: str = "lstm",
    epochs: int = 50,
    checkpoint_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick training function with checkpoint support.
    
    Args:
        model: Model to train
        train_data: Training data
        val_data: Validation data
        model_name: Model name
        model_type: "lstm" or "transformer"
        epochs: Number of epochs
        checkpoint_dir: Checkpoint directory
    
    Returns:
        Training results
    """
    if not TORCH_AVAILABLE:
        return {"error": "PyTorch not available"}
    
    # Create dataset
    class SimpleDataset(Dataset):
        def __init__(self, data, seq_len=48, horizon=24):
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
    
    # Create data loaders
    train_dataset = SimpleDataset(train_data)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    
    val_loader = None
    if val_data is not None:
        val_dataset = SimpleDataset(val_data)
        val_loader = DataLoader(val_dataset, batch_size=32)
    
    # Setup pipeline
    pipeline = TrainingPipeline(checkpoint_dir=checkpoint_dir)
    
    config = pipeline.create_training_config(
        model_name=model_name,
        model_type=model_type,
        epochs=epochs,
        batch_size=32,
        learning_rate=0.001
    )
    
    exp_id = pipeline.start_experiment(config)
    
    # Train
    results = pipeline.train(
        experiment_id=exp_id,
        model=model,
        train_loader=train_loader,
        val_loader=val_loader
    )
    
    return results
