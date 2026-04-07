"""Wilson Score Interval — Bayesian Confidence for Binary Events."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
import math

logger = logging.getLogger(__name__)


@dataclass
class WilsonResult:
    """Wilson score interval result."""
    observed_ratio: float
    lower_bound: float
    upper_bound: float
    confidence: float
    n: int
    z: float


class WilsonScoreInterval:
    """
    Wilson Score Interval for binary event confidence estimation.
    
    Used for presence detection, success rates, and binary classification confidence.
    Implements Bayesian approach with normal approximation.
    """

    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize Wilson scorer.
        
        Args:
            confidence_level: Confidence level (default 0.95 = 95%)
        """
        self._confidence_level = confidence_level
        self._z_score = self._calculate_z_score(confidence_level)

    def _calculate_z_score(self, confidence: float) -> float:
        """Calculate z-score for confidence level."""
        # Standard z-scores for common confidence levels
        z_scores = {
            0.90: 1.645,
            0.95: 1.96,
            0.99: 2.576,
        }
        return z_scores.get(confidence, 1.96)

    def calculate(
        self,
        successes: int,
        trials: int,
    ) -> WilsonResult:
        """
        Calculate Wilson score interval.
        
        Args:
            successes: Number of positive observations
            trials: Total number of observations
        
        Returns:
            WilsonResult with lower/upper bounds
        """
        if trials == 0:
            return WilsonResult(
                observed_ratio=0.0,
                lower_bound=0.0,
                upper_bound=1.0,
                confidence=0.0,
                n=0,
                z=self._z_score,
            )
        
        p_hat = successes / trials
        
        # Wilson score interval formula
        denominator = 1 + self._z_score**2 / trials
        center = (p_hat + self._z_score**2 / (2 * trials)) / denominator
        margin = (
            self._z_score
            * math.sqrt(
                (p_hat * (1 - p_hat) + self._z_score**2 / (4 * trials)) / trials
            )
        ) / denominator
        
        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)
        
        # Confidence increases with sample size
        confidence = min(1.0, trials / 100.0)
        
        result = WilsonResult(
            observed_ratio=p_hat,
            lower_bound=lower,
            upper_bound=upper,
            confidence=confidence,
            n=trials,
            z=self._z_score,
        )
        
        logger.debug(f"Wilson: {successes}/{trials} → [{lower:.3f}, {upper:.3f}]")
        return result

    def bayesian_update(
        self,
        prior_alpha: float,
        prior_beta: float,
        successes: int,
        trials: int,
    ) -> dict:
        """
        Bayesian update with Beta prior.
        
        Args:
            prior_alpha: Prior successes (alpha parameter)
            prior_beta: Prior failures (beta parameter)
            successes: Observed successes
            trials: Total trials
        
        Returns:
            Posterior parameters and credible interval
        """
        # Conjugate prior: Beta(α, β)
        posterior_alpha = prior_alpha + successes
        posterior_beta = prior_beta + (trials - successes)
        
        # Posterior mean
        posterior_mean = posterior_alpha / (posterior_alpha + posterior_beta)
        
        # Posterior variance
        n = posterior_alpha + posterior_beta
        posterior_var = (posterior_alpha * posterior_beta) / (n**2 * (n + 1))
        
        # 95% credible interval (approximation)
        std = math.sqrt(posterior_var)
        lower = max(0.0, posterior_mean - 1.96 * std)
        upper = min(1.0, posterior_mean + 1.96 * std)
        
        return {
            "prior": {"alpha": prior_alpha, "beta": prior_beta},
            "posterior": {"alpha": posterior_alpha, "beta": posterior_beta},
            "mean": posterior_mean,
            "variance": posterior_var,
            "credible_interval_95": [lower, upper],
        }


# Global default Wilson scorer
default_wilson_scorer: Optional[WilsonScoreInterval] = None


def init_wilson_scorer(confidence: float = 0.95) -> WilsonScoreInterval:
    """Initialize global Wilson scorer."""
    global default_wilson_scorer
    default_wilson_scorer = WilsonScoreInterval(confidence_level=confidence)
    return default_wilson_scorer
