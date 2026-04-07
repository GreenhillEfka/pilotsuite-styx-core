"""Wilson Score Interval for confidence-bounded presence detection.

The Wilson Score Interval provides a statistically robust way to estimate
presence probability from binary sensor readings, accounting for sample size
and providing confidence bounds. This prevents overconfidence when few
observations are available.

References:
- Wilson, E. B. (1927). "Probable inference, the law of succession, and statistical inference"
- Wikipedia: "Binomial proportion confidence interval"
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class WilsonInterval:
    """Wilson Score Interval result."""
    
    lower_bound: float  # Lower bound of confidence interval
    upper_bound: float  # Upper bound of confidence interval
    center: float       # Point estimate (center of interval)
    confidence_level: float  # Confidence level (e.g., 0.95)
    successes: int      # Number of positive observations
    trials: int         # Total number of observations
    width: float        # Width of the interval (uncertainty measure)
    
    @property
    def is_reliable(self) -> bool:
        """Check if interval is sufficiently narrow for decisions."""
        # Consider reliable if width < 0.3 (adjustable threshold)
        return self.width < 0.3
    
    def __str__(self) -> str:
        return (
            f"WilsonInterval(center={self.center:.3f}, "
            f"[{self.lower_bound:.3f}, {self.upper_bound:.3f}], "
            f"n={self.trials}, conf={self.confidence_level:.2f})"
        )


class WilsonScoreInterval:
    """Calculate Wilson Score Intervals for presence detection.
    
    The Wilson Score Interval is superior to the normal approximation
    (Wald interval) especially for:
    - Small sample sizes
    - Proportions near 0 or 1
    - When confidence bounds are critical for decision-making
    
    Formula:
        p̂ = (X + z²/2n) / (1 + z²/n)
        margin = z * sqrt((p̂(1-p̂) + z²/4n) / n) / (1 + z²/n)
        
        where:
        - X = number of successes (positive detections)
        - n = total trials (observations)
        - z = z-score for confidence level (1.96 for 95%)
    """
    
    # Common z-scores for confidence levels
    Z_SCORES = {
        0.90: 1.645,
        0.95: 1.96,
        0.99: 2.576,
        0.997: 3.0,  # 3-sigma
    }
    
    def __init__(self, confidence_level: float = 0.95):
        """Initialize with confidence level.
        
        Args:
            confidence_level: Confidence level (0.90, 0.95, 0.99, etc.)
        """
        if confidence_level not in self.Z_SCORES:
            # Interpolate or use closest
            self._z = self._calculate_z(confidence_level)
        else:
            self._z = self.Z_SCORES[confidence_level]
        
        self._confidence_level = confidence_level
        logger.debug(f"WilsonScoreInterval initialized with conf={confidence_level}, z={self._z:.3f}")
    
    def _calculate_z(self, confidence_level: float) -> float:
        """Calculate z-score from confidence level using normal distribution.
        
        For production, consider using scipy.stats.norm.ppf((1 + cl) / 2)
        Here we use a simple approximation.
        """
        # Approximation: z ≈ sqrt(2) * erf_inv(confidence_level)
        # Using lookup with interpolation
        levels = sorted(self.Z_SCORES.keys())
        if confidence_level <= levels[0]:
            return self.Z_SCORES[levels[0]]
        if confidence_level >= levels[-1]:
            return self.Z_SCORES[levels[-1]]
        
        # Linear interpolation
        for i in range(len(levels) - 1):
            if levels[i] <= confidence_level <= levels[i + 1]:
                t = (confidence_level - levels[i]) / (levels[i + 1] - levels[i])
                return self.Z_SCORES[levels[i]] + t * (self.Z_SCORES[levels[i + 1]] - self.Z_SCORES[levels[i]])
        
        return self.Z_SCORES[0.95]  # Fallback
    
    def calculate(
        self,
        successes: int,
        trials: int,
        confidence_level: Optional[float] = None
    ) -> WilsonInterval:
        """Calculate Wilson Score Interval.
        
        Args:
            successes: Number of positive observations (detections)
            trials: Total number of observations
            confidence_level: Override default confidence level
            
        Returns:
            WilsonInterval with bounds and metadata
            
        Raises:
            ValueError: If trials <= 0 or successes > trials
        """
        if trials <= 0:
            raise ValueError("trials must be positive")
        if successes > trials or successes < 0:
            raise ValueError("successes must be between 0 and trials")
        
        z = self._z
        if confidence_level is not None:
            z = self._calculate_z(confidence_level)
        
        n = trials
        X = successes
        
        # Wilson Score Interval formula
        z2 = z * z
        denominator = 1 + z2 / n
        
        # Center (adjusted proportion)
        p_tilde = (X + z2 / 2) / (n + z2)
        
        # Margin of error
        standard_error = math.sqrt((p_tilde * (1 - p_tilde) + z2 / (4 * n)) / n)
        margin = z * standard_error / denominator
        
        lower = max(0.0, p_tilde - margin)
        upper = min(1.0, p_tilde + margin)
        width = upper - lower
        
        interval = WilsonInterval(
            lower_bound=lower,
            upper_bound=upper,
            center=p_tilde,
            confidence_level=confidence_level or self._confidence_level,
            successes=successes,
            trials=trials,
            width=width,
        )
        
        logger.debug(
            f"Wilson interval: X={X}, n={n} → {interval}"
        )
        
        return interval
    
    def calculate_from_rate(
        self,
        observed_rate: float,
        trials: int,
        confidence_level: Optional[float] = None
    ) -> WilsonInterval:
        """Calculate interval from observed rate and sample size.
        
        Args:
            observed_rate: Observed proportion (0 to 1)
            trials: Number of observations
            confidence_level: Override default confidence level
            
        Returns:
            WilsonInterval
        """
        successes = round(observed_rate * trials)
        return self.calculate(successes, trials, confidence_level)
    
    def probability_above_threshold(
        self,
        successes: int,
        trials: int,
        threshold: float
    ) -> float:
        """Estimate probability that true rate exceeds threshold.
        
        Uses the Wilson interval to make a conservative estimate.
        If threshold is below lower bound, probability is high (>0.975 for 95% CI).
        If threshold is above upper bound, probability is low (<0.025 for 95% CI).
        If threshold is within interval, use linear interpolation.
        
        Args:
            successes: Number of positive observations
            trials: Total observations
            threshold: Threshold to compare against
            
        Returns:
            Estimated probability (0 to 1) that true rate > threshold
        """
        interval = self.calculate(successes, trials)
        
        if threshold <= interval.lower_bound:
            # Very likely above threshold
            return 1.0 - (1 - interval.confidence_level) / 2
        elif threshold >= interval.upper_bound:
            # Very unlikely above threshold
            return (1 - interval.confidence_level) / 2
        else:
            # Within interval - linear interpolation
            t_normalized = (threshold - interval.lower_bound) / interval.width
            # Map from [lower, upper] to [high_prob, low_prob]
            high_prob = 1.0 - (1 - interval.confidence_level) / 2
            low_prob = (1 - interval.confidence_level) / 2
            return high_prob - t_normalized * (high_prob - low_prob)
    
    def compare_intervals(
        self,
        successes1: int,
        trials1: int,
        successes2: int,
        trials2: int
    ) -> Tuple[float, bool]:
        """Compare two Wilson intervals to determine if they're significantly different.
        
        Args:
            successes1, trials1: First sample
            successes2, trials2: Second sample
            
        Returns:
            Tuple of (overlap_ratio, is_significantly_different)
            - overlap_ratio: 0.0 = no overlap, 1.0 = complete overlap
            - is_significantly_different: True if intervals don't overlap much
        """
        interval1 = self.calculate(successes1, trials1)
        interval2 = self.calculate(successes2, trials2)
        
        # Calculate overlap
        overlap_start = max(interval1.lower_bound, interval2.lower_bound)
        overlap_end = min(interval1.upper_bound, interval2.upper_bound)
        
        if overlap_start >= overlap_end:
            # No overlap
            return 0.0, True
        
        overlap = overlap_end - overlap_start
        # Normalize by average width
        avg_width = (interval1.width + interval2.width) / 2
        overlap_ratio = overlap / avg_width if avg_width > 0 else 0.0
        
        # Consider significantly different if overlap < 20% of average width
        is_different = overlap_ratio < 0.2
        
        return min(1.0, overlap_ratio), is_different


# Convenience function for quick calculations
def wilson_score(
    successes: int,
    trials: int,
    confidence: float = 0.95
) -> WilsonInterval:
    """Calculate Wilson Score Interval with default settings.
    
    Args:
        successes: Number of positive observations
        trials: Total observations
        confidence: Confidence level (default 0.95)
        
    Returns:
        WilsonInterval
    """
    calculator = WilsonScoreInterval(confidence_level=confidence)
    return calculator.calculate(successes, trials)
