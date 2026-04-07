"""Base ML Model Interface for PilotSuite.

Provides abstract base class for all ML models in the pipeline.
Migrated from pilotsuite-styx-ha (pure logic, no HA dependencies).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseMLModel(ABC):
    """Abstract base class for all ML models."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._is_fitted = False

    @abstractmethod
    def fit(self, X, y=None):
        """Train the model with training data."""
        pass

    @abstractmethod
    def update(self, X, y=None):
        """Update model with new data (incremental learning)."""
        pass

    @abstractmethod
    def reset(self):
        """Reset model to initial untrained state."""
        pass

    @abstractmethod
    def get_model_summary(self) -> Dict[str, Any]:
        """Return model metadata and statistics."""
        pass

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    @is_fitted.setter
    def is_fitted(self, value: bool):
        self._is_fitted = value
