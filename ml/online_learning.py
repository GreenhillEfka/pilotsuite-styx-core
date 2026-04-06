"""
Online Learning Module - Continuous Model Updates

Enables models to learn incrementally from streaming data without retraining
from scratch. Supports concept drift detection and adaptive learning rates.
"""
from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Callable, Deque
from dataclasses import dataclass, field
from collections import deque
import threading
import time
from datetime import datetime
import json
import os


@dataclass
class OnlineLearningConfig:
    """Configuration for online learning."""
    learning_rate: float = 0.01
    learning_rate_decay: float = 0.999
    min_learning_rate: float = 1e-6
    batch_size: int = 1
    memory_buffer_size: int = 1000
    drift_detection_window: int = 100
    drift_threshold: float = 0.05
    regularization: float = 0.001
    momentum: float = 0.9
    adaptive_lr: bool = True  # Use Adam-style adaptive learning rates


@dataclass
class DriftEvent:
    """Represents a detected concept drift."""
    timestamp: str
    drift_score: float
    feature_indices: List[int]
    severity: str  # "low", "medium", "high"
    action_taken: str


class DriftDetector:
    """
    Concept drift detection using statistical tests.
    
    Implements ADWIN (Adaptive Windowing) and Page-Hinkley tests.
    """
    
    def __init__(
        self,
        window_size: int = 100,
        threshold: float = 0.05,
        min_instances: int = 30
    ):
        """
        Initialize drift detector.
        
        Args:
            window_size: Size of the sliding window
            threshold: Threshold for drift detection
            min_instances: Minimum instances before checking for drift
        """
        self.window_size = window_size
        self.threshold = threshold
        self.min_instances = min_instances
        self._error_window: Deque[float] = deque(maxlen=window_size)
        self._baseline_mean: Optional[float] = None
        self._baseline_std: Optional[float] = None
        self._drift_count = 0
        self._lock = threading.Lock()
        
    def add_instance(self, error: float) -> bool:
        """
        Add a new instance and check for drift.
        
        Args:
            error: Prediction error for this instance
            
        Returns:
            True if drift detected
        """
        with self._lock:
            self._error_window.append(error)
            
            if len(self._error_window) < self.min_instances:
                return False
                
            # Compute current statistics
            current_mean = np.mean(self._error_window)
            current_std = np.std(self._error_window) + 1e-8
            
            # Initialize baseline if needed
            if self._baseline_mean is None:
                self._baseline_mean = current_mean
                self._baseline_std = current_std
                return False
                
            # Check for drift using z-test
            z_score = abs(current_mean - self._baseline_mean) / (
                self._baseline_std / np.sqrt(len(self._error_window))
            )
            
            if z_score > self.threshold:
                self._drift_count += 1
                # Reset baseline after drift
                self._baseline_mean = current_mean
                self._baseline_std = current_std
                return True
                
            # Update baseline with exponential moving average
            alpha = 0.1
            self._baseline_mean = alpha * current_mean + (1 - alpha) * self._baseline_mean
            self._baseline_std = alpha * current_std + (1 - alpha) * self._baseline_std
            
            return False
            
    def get_drift_score(self) -> float:
        """Get current drift score."""
        if len(self._error_window) < self.min_instances:
            return 0.0
            
        current_mean = np.mean(self._error_window)
        if self._baseline_mean is None:
            return 0.0
            
        return abs(current_mean - self._baseline_mean) / (self._baseline_std + 1e-8)
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            "window_size": len(self._error_window),
            "baseline_mean": self._baseline_mean,
            "baseline_std": self._baseline_std,
            "drift_count": self._drift_count,
            "current_drift_score": self.get_drift_score()
        }
        
    def reset(self) -> None:
        """Reset detector state."""
        self._error_window.clear()
        self._baseline_mean = None
        self._baseline_std = None


class AdaptiveLearningRate:
    """
    Adaptive learning rate scheduler.
    
    Implements Adam-style per-parameter adaptive learning rates.
    """
    
    def __init__(
        self,
        base_lr: float = 0.01,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
        decay: float = 0.999,
        min_lr: float = 1e-6
    ):
        """Initialize adaptive LR scheduler."""
        self.base_lr = base_lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.decay = decay
        self.min_lr = min_lr
        
        self._m: Optional[np.ndarray] = None  # First moment
        self._v: Optional[np.ndarray] = None  # Second moment
        self._t = 0  # Time step
        self._current_lr = base_lr
        self._lock = threading.Lock()
        
    def update(self, gradients: np.ndarray) -> np.ndarray:
        """
        Update learning rate based on gradients.
        
        Returns:
            Effective learning rates for each parameter
        """
        with self._lock:
            self._t += 1
            
            # Initialize moments if needed
            if self._m is None:
                self._m = np.zeros_like(gradients)
                self._v = np.zeros_like(gradients)
                
            # Update moments
            self._m = self.beta1 * self._m + (1 - self.beta1) * gradients
            self._v = self.beta2 * self._v + (1 - self.beta2) * (gradients ** 2)
            
            # Bias correction
            m_hat = self._m / (1 - self.beta1 ** self._t)
            v_hat = self._v / (1 - self.beta2 ** self._t)
            
            # Compute adaptive learning rates
            lr = self.base_lr * (self.decay ** self._t)
            lr = max(lr, self.min_lr)
            
            adaptive_lrs = lr / (np.sqrt(v_hat) + self.epsilon)
            
            return adaptive_lrs
            
    def get_current_lr(self) -> float:
        """Get current base learning rate."""
        return self.base_lr * (self.decay ** self._t)
        
    def reset(self) -> None:
        """Reset scheduler state."""
        self._m = None
        self._v = None
        self._t = 0


class OnlineLearner:
    """
    Online learning model with incremental updates.
    
    Supports various base models and online optimization algorithms.
    """
    
    def __init__(
        self,
        input_size: int,
        output_size: int = 1,
        config: Optional[OnlineLearningConfig] = None
    ):
        """
        Initialize online learner.
        
        Args:
            input_size: Number of input features
            output_size: Number of output targets
            config: Learning configuration
        """
        self.input_size = input_size
        self.output_size = output_size
        self.config = config or OnlineLearningConfig()
        
        # Model weights
        self._weights = np.random.randn(input_size, output_size) * 0.1
        self._bias = np.zeros((1, output_size))
        
        # Momentum buffers
        self._velocity_w = np.zeros_like(self._weights)
        self._velocity_b = np.zeros_like(self._bias)
        
        # Adaptive learning rate
        self._adaptive_lr = AdaptiveLearningRate(
            base_lr=self.config.learning_rate,
            decay=self.config.learning_rate_decay,
            min_lr=self.config.min_learning_rate
        ) if self.config.adaptive_lr else None
        
        # Drift detection
        self._drift_detector = DriftDetector(
            window_size=self.config.drift_detection_window,
            threshold=self.config.drift_threshold
        )
        
        # Memory buffer for experience replay
        self._memory_buffer: Deque[Tuple[np.ndarray, np.ndarray]] = deque(
            maxlen=self.config.memory_buffer_size
        )
        
        # Metrics
        self._total_updates = 0
        self._drift_events: List[DriftEvent] = []
        self._loss_history: Deque[float] = deque(maxlen=1000)
        self._lock = threading.Lock()
        
        # Callbacks
        self._drift_callbacks: List[Callable[[DriftEvent], None]] = []
        self._update_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
    def partial_fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: Optional[np.ndarray] = None
    ) -> Dict[str, float]:
        """
        Incrementally update model with new data.
        
        Args:
            X: Input features (batch_size, input_size)
            y: Target values (batch_size, output_size)
            sample_weight: Optional sample weights
            
        Returns:
            Metrics dictionary
        """
        with self._lock:
            batch_size = len(X)
            
            # Forward pass
            predictions = self._forward(X)
            
            # Compute loss
            loss = np.mean((predictions - y) ** 2)
            self._loss_history.append(loss)
            
            # Check for drift
            for pred, target in zip(predictions, y):
                error = np.mean((pred - target) ** 2)
                if self._drift_detector.add_instance(error):
                    drift_event = self._handle_drift(X, y, error)
                    for callback in self._drift_callbacks:
                        callback(drift_event)
                        
            # Compute gradients
            gradients_w = 2 * X.T @ (predictions - y) / batch_size
            gradients_b = 2 * np.mean(predictions - y, axis=0, keepdims=True)
            
            # Add regularization
            gradients_w += self.config.regularization * self._weights
            
            # Apply momentum and adaptive learning rate
            if self._adaptive_lr:
                adaptive_lrs = self._adaptive_lr.update(gradients_w)
                update_w = adaptive_lrs * gradients_w
                update_b = self.config.learning_rate * gradients_b
            else:
                # SGD with momentum
                self._velocity_w = (
                    self.config.momentum * self._velocity_w +
                    self.config.learning_rate * gradients_w
                )
                self._velocity_b = (
                    self.config.momentum * self._velocity_b +
                    self.config.learning_rate * gradients_b
                )
                update_w = self._velocity_w
                update_b = self._velocity_b
                
            # Update weights
            self._weights -= update_w
            self._bias -= update_b
            
            # Store in memory buffer
            for xi, yi in zip(X, y):
                self._memory_buffer.append((xi.copy(), yi.copy()))
                
            self._total_updates += 1
            
            metrics = {
                "loss": float(loss),
                "mae": float(np.mean(np.abs(predictions - y))),
                "updates": self._total_updates,
                "learning_rate": self._adaptive_lr.get_current_lr() if self._adaptive_lr else self.config.learning_rate,
                "drift_detected": len(self._drift_events)
            }
            
            # Notify callbacks
            for callback in self._update_callbacks:
                callback(metrics)
                
            return metrics
            
    def _forward(self, X: np.ndarray) -> np.ndarray:
        """Forward pass."""
        return X @ self._weights + self._bias
        
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions."""
        with self._lock:
            return self._forward(X)
            
    def _handle_drift(
        self,
        X: np.ndarray,
        y: np.ndarray,
        error: float
    ) -> DriftEvent:
        """Handle detected concept drift."""
        # Determine severity
        if error > 2 * self.config.drift_threshold:
            severity = "high"
            action = "increase_learning_rate"
            if self._adaptive_lr:
                self._adaptive_lr.base_lr = min(
                    self._adaptive_lr.base_lr * 2,
                    0.1
                )
        elif error > 1.5 * self.config.drift_threshold:
            severity = "medium"
            action = "replay_memory_buffer"
            self._replay_memory()
        else:
            severity = "low"
            action = "monitor"
            
        drift_event = DriftEvent(
            timestamp=datetime.utcnow().isoformat(),
            drift_score=error,
            feature_indices=self._identify_drift_features(X, y),
            severity=severity,
            action_taken=action
        )
        
        self._drift_events.append(drift_event)
        
        # Keep only last 100 drift events
        if len(self._drift_events) > 100:
            self._drift_events = self._drift_events[-100:]
            
        return drift_event
        
    def _identify_drift_features(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> List[int]:
        """Identify which features are contributing to drift."""
        if len(self._memory_buffer) < 10:
            return list(range(self.input_size))
            
        # Compare current feature statistics with historical
        historical_X = np.array([x for x, _ in self._memory_buffer])
        
        current_means = np.mean(X, axis=0)
        historical_means = np.mean(historical_X, axis=0)
        
        current_stds = np.std(X, axis=0) + 1e-8
        historical_stds = np.std(historical_X, axis=0) + 1e-8
        
        # Z-score for each feature
        z_scores = np.abs(current_means - historical_means) / (
            historical_stds / np.sqrt(len(X))
        )
        
        # Return features with significant drift
        drifted_features = np.where(z_scores > self.config.drift_threshold)[0]
        return drifted_features.tolist()
        
    def _replay_memory(self, batch_size: int = 32) -> None:
        """Replay samples from memory buffer to adapt to drift."""
        if len(self._memory_buffer) < batch_size:
            return
            
        indices = np.random.choice(len(self._memory_buffer), batch_size, replace=False)
        X_batch = np.array([self._memory_buffer[i][0] for i in indices])
        y_batch = np.array([self._memory_buffer[i][1] for i in indices])
        
        # Perform update with reduced learning rate
        old_lr = self.config.learning_rate
        self.config.learning_rate *= 0.5
        self.partial_fit(X_batch, y_batch)
        self.config.learning_rate = old_lr
        
    def get_weights(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get current model weights."""
        with self._lock:
            return self._weights.copy(), self._bias.copy()
            
    def set_weights(self, weights: np.ndarray, bias: np.ndarray) -> None:
        """Set model weights."""
        with self._lock:
            self._weights = weights.copy()
            self._bias = bias.copy()
            
    def get_drift_history(self) -> List[Dict[str, Any]]:
        """Get drift event history."""
        return [
            {
                "timestamp": e.timestamp,
                "drift_score": e.drift_score,
                "severity": e.severity,
                "action": e.action_taken,
                "affected_features": e.feature_indices
            }
            for e in self._drift_events
        ]
        
    def get_loss_history(self) -> List[float]:
        """Get loss history."""
        return list(self._loss_history)
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get learner statistics."""
        return {
            "total_updates": self._total_updates,
            "memory_buffer_size": len(self._memory_buffer),
            "drift_events": len(self._drift_events),
            "current_loss": self._loss_history[-1] if self._loss_history else None,
            "avg_loss": np.mean(self._loss_history) if self._loss_history else None,
            "learning_rate": self._adaptive_lr.get_current_lr() if self._adaptive_lr else self.config.learning_rate,
            "drift_detector": self._drift_detector.get_statistics()
        }
        
    def save(self, path: str) -> None:
        """Save model state."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "weights": self._weights.tolist(),
            "bias": self._bias.tolist(),
            "total_updates": self._total_updates,
            "drift_events": self.get_drift_history(),
            "config": {
                "input_size": self.input_size,
                "output_size": self.output_size,
                "learning_rate": self.config.learning_rate,
                "drift_threshold": self.config.drift_threshold
            }
        }
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
            
    def load(self, path: str) -> None:
        """Load model state."""
        with open(path, "r") as f:
            state = json.load(f)
            
        self._weights = np.array(state["weights"])
        self._bias = np.array(state["bias"])
        self._total_updates = state["total_updates"]


class ContinuousModelUpdater:
    """
    Manages continuous model updates across multiple online learners.
    
    Coordinates updates, handles versioning, and manages update schedules.
    """
    
    def __init__(self, update_interval_seconds: float = 60.0):
        """
        Initialize updater.
        
        Args:
            update_interval_seconds: Interval between update cycles
        """
        self.update_interval = update_interval_seconds
        self._learners: Dict[str, OnlineLearner] = {}
        self._update_queue: Deque[Dict[str, Any]] = deque()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._update_history: List[Dict[str, Any]] = []
        
    def register_learner(self, name: str, learner: OnlineLearner) -> None:
        """Register an online learner for continuous updates."""
        with self._lock:
            self._learners[name] = learner
            
    def unregister_learner(self, name: str) -> None:
        """Unregister a learner."""
        with self._lock:
            self._learners.pop(name, None)
            
    def queue_update(
        self,
        learner_name: str,
        X: np.ndarray,
        y: np.ndarray,
        priority: int = 0
    ) -> None:
        """Queue an update for a learner."""
        self._update_queue.append({
            "learner_name": learner_name,
            "X": X,
            "y": y,
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Sort by priority
        sorted_queue = sorted(
            self._update_queue,
            key=lambda x: x["priority"],
            reverse=True
        )
        self._update_queue.clear()
        self._update_queue.extend(sorted_queue)
        
    def start(self) -> None:
        """Start the continuous update loop."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        
    def stop(self) -> None:
        """Stop the update loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            
    def _update_loop(self) -> None:
        """Main update loop."""
        while self._running:
            try:
                self._process_updates()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Update loop error: {e}")
                time.sleep(1.0)
                
    def _process_updates(self) -> None:
        """Process queued updates."""
        with self._lock:
            if not self._update_queue:
                return
                
            # Process up to 10 updates per cycle
            for _ in range(min(10, len(self._update_queue))):
                update = self._update_queue.popleft()
                learner = self._learners.get(update["learner_name"])
                
                if learner:
                    metrics = learner.partial_fit(update["X"], update["y"])
                    
                    self._update_history.append({
                        "learner": update["learner_name"],
                        "metrics": metrics,
                        "timestamp": update["timestamp"]
                    })
                    
    def get_status(self) -> Dict[str, Any]:
        """Get updater status."""
        return {
            "running": self._running,
            "queue_size": len(self._update_queue),
            "learners": list(self._learners.keys()),
            "total_updates": len(self._update_history),
            "update_interval": self.update_interval
        }


class StreamingDataProcessor:
    """
    Real-time streaming data processor for online learning.
    
    Handles data ingestion, preprocessing, and batching for continuous learning.
    """
    
    def __init__(
        self,
        batch_size: int = 32,
        max_wait_seconds: float = 5.0
    ):
        """
        Initialize processor.
        
        Args:
            batch_size: Target batch size
            max_wait_seconds: Maximum wait time before flushing partial batch
        """
        self.batch_size = batch_size
        self.max_wait = max_wait_seconds
        
        self._buffer: Deque[Tuple[np.ndarray, np.ndarray]] = deque()
        self._last_flush = time.time()
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[np.ndarray, np.ndarray], None]] = []
        
    def add_sample(self, X: np.ndarray, y: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Add a sample to the buffer.
        
        Returns:
            Batch if buffer is full, None otherwise
        """
        with self._lock:
            self._buffer.append((X.copy(), y.copy()))
            
            # Check if we should flush
            should_flush = (
                len(self._buffer) >= self.batch_size or
                time.time() - self._last_flush > self.max_wait
            )
            
            if should_flush and len(self._buffer) > 0:
                return self._flush()
                
            return None
            
    def _flush(self) -> Tuple[np.ndarray, np.ndarray]:
        """Flush buffer to batch."""
        samples = list(self._buffer)
        self._buffer.clear()
        self._last_flush = time.time()
        
        X_batch = np.stack([s[0] for s in samples])
        y_batch = np.stack([s[1] for s in samples])
        
        # Notify callbacks
        for callback in self._callbacks:
            callback(X_batch, y_batch)
            
        return X_batch, y_batch
        
    def register_callback(
        self,
        callback: Callable[[np.ndarray, np.ndarray], None]
    ) -> None:
        """Register a callback for when batches are ready."""
        self._callbacks.append(callback)
        
    def get_buffer_size(self) -> int:
        """Get current buffer size."""
        return len(self._buffer)
        
    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._buffer.clear()
