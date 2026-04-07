"""
Feature Extractor for Time Series Sensor Data

Extracts statistical, temporal, and frequency-domain features from sensor readings
for use in anomaly detection models.

Features:
- Statistical: mean, std, min, max, percentiles, skewness, kurtosis
- Temporal: trends, autocorrelation, lag features
- Frequency: FFT-based features (optional)
- Rolling windows for incremental feature computation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for feature extraction."""
    
    # Window sizes for rolling features (in samples)
    short_window: int = 10
    medium_window: int = 50
    long_window: int = 200
    
    # Lag features
    max_lag: int = 10
    
    # Percentiles to compute
    percentiles: List[float] = field(default_factory=lambda: [0.1, 0.25, 0.5, 0.75, 0.9])
    
    # Include frequency domain features
    include_frequency: bool = False
    
    # Minimum samples required for feature extraction
    min_samples: int = 5


@dataclass
class ExtractedFeatures:
    """Container for extracted features from a time series window."""
    
    # Basic statistics
    mean: float
    std: float
    min_val: float
    max_val: float
    range_val: float
    
    # Percentiles
    percentiles: Dict[str, float]
    
    # Distribution shape
    skewness: float
    kurtosis: float
    
    # Temporal features
    trend: float  # Linear trend coefficient
    autocorrelation: float  # Lag-1 autocorrelation
    
    # Rate of change
    roc_mean: float
    roc_std: float
    roc_max: float
    
    # Lag features
    lag_features: Dict[str, float]
    
    # Metadata
    timestamp: datetime
    sample_count: int
    window_size: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to flat dictionary for ML model input."""
        features = {
            "mean": self.mean,
            "std": self.std,
            "min": self.min_val,
            "max": self.max_val,
            "range": self.range_val,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "trend": self.trend,
            "autocorrelation": self.autocorrelation,
            "roc_mean": self.roc_mean,
            "roc_std": self.roc_std,
            "roc_max": self.roc_max,
            "sample_count": self.sample_count,
        }
        
        # Add percentiles
        for name, value in self.percentiles.items():
            features[f"p_{name}"] = value
        
        # Add lag features
        for lag, value in self.lag_features.items():
            features[f"lag_{lag}"] = value
        
        return features
    
    def to_array(self, feature_names: Optional[List[str]] = None) -> np.ndarray:
        """Convert to numpy array in specified order."""
        feature_dict = self.to_dict()
        if feature_names:
            return np.array([feature_dict.get(name, 0.0) for name in feature_names])
        return np.array(list(feature_dict.values()))


class FeatureExtractor:
    """
    Extracts features from time series sensor data.
    
    Supports:
    - Batch feature extraction from complete windows
    - Incremental feature updates for streaming data
    - Multi-sensor feature aggregation
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        self._feature_names: Optional[List[str]] = None
        
    def extract(self, values: np.ndarray, timestamps: Optional[np.ndarray] = None) -> ExtractedFeatures:
        """
        Extract features from a window of sensor values.
        
        Args:
            values: Array of sensor readings (1D)
            timestamps: Optional array of timestamps for time-based features
            
        Returns:
            ExtractedFeatures object with all computed features
            
        Raises:
            ValueError: If insufficient samples provided
        """
        if len(values) < self.config.min_samples:
            raise ValueError(
                f"Insufficient samples: {len(values)} < {self.config.min_samples}"
            )
        
        values = np.asarray(values, dtype=np.float64)
        
        # Handle NaN values
        valid_mask = ~np.isnan(values)
        if np.sum(valid_mask) < self.config.min_samples:
            raise ValueError("Too many NaN values in input")
        
        values_clean = values[valid_mask]
        
        # Basic statistics
        mean_val = np.mean(values_clean)
        std_val = np.std(values_clean)
        min_val = np.min(values_clean)
        max_val = np.max(values_clean)
        range_val = max_val - min_val
        
        # Percentiles
        percentiles = {}
        for p in self.config.percentiles:
            p_name = "p_" + str(p).replace(".", "_")
            percentiles[p_name] = float(np.percentile(values_clean, p * 100))
        
        # Distribution shape
        skewness = float(scipy_stats.skew(values_clean))
        kurtosis = float(scipy_stats.kurtosis(values_clean))
        
        # Temporal features
        trend = self._compute_trend(values_clean)
        autocorr = self._compute_autocorrelation(values_clean)
        
        # Rate of change
        roc = np.diff(values_clean)
        roc_mean = float(np.mean(roc)) if len(roc) > 0 else 0.0
        roc_std = float(np.std(roc)) if len(roc) > 0 else 0.0
        roc_max = float(np.max(np.abs(roc))) if len(roc) > 0 else 0.0
        
        # Lag features
        lag_features = self._compute_lag_features(values_clean)
        
        return ExtractedFeatures(
            mean=mean_val,
            std=std_val,
            min_val=min_val,
            max_val=max_val,
            range_val=range_val,
            percentiles=percentiles,
            skewness=skewness,
            kurtosis=kurtosis,
            trend=trend,
            autocorrelation=autocorr,
            roc_mean=roc_mean,
            roc_std=roc_std,
            roc_max=roc_max,
            lag_features=lag_features,
            timestamp=datetime.now(timezone.utc),
            sample_count=len(values_clean),
            window_size=len(values),
        )
    
    def extract_rolling(
        self,
        values: np.ndarray,
        window_size: Optional[int] = None
    ) -> List[ExtractedFeatures]:
        """
        Extract features using a rolling window approach.
        
        Args:
            values: Array of sensor readings
            window_size: Size of rolling window (uses config default if not specified)
            
        Returns:
            List of ExtractedFeatures for each window position
        """
        window_size = window_size or self.config.medium_window
        
        if len(values) < window_size:
            # Not enough data for rolling window, extract from full series
            return [self.extract(values)]
        
        features_list = []
        for i in range(len(values) - window_size + 1):
            window = values[i:i + window_size]
            try:
                features = self.extract(window)
                features_list.append(features)
            except ValueError:
                # Skip windows with too many NaN values
                continue
        
        return features_list
    
    def extract_multi_sensor(
        self,
        sensor_data: Dict[str, np.ndarray]
    ) -> Dict[str, ExtractedFeatures]:
        """
        Extract features from multiple sensors simultaneously.
        
        Args:
            sensor_data: Dictionary mapping sensor IDs to value arrays
            
        Returns:
            Dictionary mapping sensor IDs to their extracted features
        """
        result = {}
        for sensor_id, values in sensor_data.items():
            try:
                result[sensor_id] = self.extract(values)
            except ValueError as e:
                logger.warning(f"Failed to extract features for sensor {sensor_id}: {e}")
                continue
        
        return result
    
    def aggregate_features(
        self,
        features_list: List[ExtractedFeatures]
    ) -> Dict[str, float]:
        """
        Aggregate multiple feature extractions into summary statistics.
        
        Useful for creating higher-level features from window-level features.
        
        Args:
            features_list: List of ExtractedFeatures objects
            
        Returns:
            Dictionary of aggregated feature statistics
        """
        if not features_list:
            return {}
        
        # Convert to arrays
        feature_arrays = [f.to_dict() for f in features_list]
        
        aggregated = {}
        for key in feature_arrays[0].keys():
            values = [f[key] for f in feature_arrays if key in f]
            if values:
                aggregated[f"{key}_mean"] = float(np.mean(values))
                aggregated[f"{key}_std"] = float(np.std(values))
                aggregated[f"{key}_min"] = float(np.min(values))
                aggregated[f"{key}_max"] = float(np.max(values))
        
        return aggregated
    
    def _compute_trend(self, values: np.ndarray) -> float:
        """Compute linear trend coefficient using least squares."""
        if len(values) < 2:
            return 0.0
        
        x = np.arange(len(values))
        # Normalize x to avoid numerical issues
        x_norm = (x - np.mean(x)) / (np.std(x) + 1e-10)
        
        # Linear regression: y = ax + b
        try:
            slope, _, _, _, _ = scipy_stats.linregress(x_norm, values)
            return float(slope)
        except Exception:
            return 0.0
    
    def _compute_autocorrelation(self, values: np.ndarray, lag: int = 1) -> float:
        """Compute autocorrelation at specified lag."""
        if len(values) < lag + 2:
            return 0.0
        
        n = len(values)
        mean = np.mean(values)
        var = np.var(values)
        
        if var < 1e-10:
            return 0.0
        
        # Autocorrelation formula
        autocorr = np.sum((values[:n-lag] - mean) * (values[lag:] - mean)) / ((n - lag) * var)
        return float(autocorr)
    
    def _compute_lag_features(self, values: np.ndarray) -> Dict[str, float]:
        """Compute lag features up to max_lag."""
        lag_features = {}
        max_lag = min(self.config.max_lag, len(values) - 1)
        
        for lag in range(1, max_lag + 1):
            lag_features[lag] = float(values[-lag]) if len(values) >= lag else 0.0
        
        return lag_features
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names produced by this extractor."""
        if self._feature_names is None:
            # Generate names from a sample extraction
            sample_features = self.extract(np.random.randn(self.config.medium_window))
            self._feature_names = list(sample_features.to_dict().keys())
        return self._feature_names.copy()
    
    def normalize_features(
        self,
        features: Dict[str, float],
        means: Dict[str, float],
        stds: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Normalize features using provided statistics.
        
        Args:
            features: Raw feature dictionary
            means: Mean values for each feature
            stds: Standard deviations for each feature
            
        Returns:
            Normalized feature dictionary
        """
        normalized = {}
        for key, value in features.items():
            mean = means.get(key, 0.0)
            std = stds.get(key, 1.0)
            if std < 1e-10:
                std = 1.0
            normalized[key] = (value - mean) / std
        return normalized


def create_feature_extractor(
    short_window: int = 10,
    medium_window: int = 50,
    long_window: int = 200,
    include_frequency: bool = False
) -> FeatureExtractor:
    """
    Factory function to create a configured FeatureExtractor.
    
    Args:
        short_window: Short-term window size
        medium_window: Medium-term window size
        long_window: Long-term window size
        include_frequency: Whether to include frequency-domain features
        
    Returns:
        Configured FeatureExtractor instance
    """
    config = FeatureConfig(
        short_window=short_window,
        medium_window=medium_window,
        long_window=long_window,
        include_frequency=include_frequency,
    )
    return FeatureExtractor(config)
