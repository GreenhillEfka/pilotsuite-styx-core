"""
Time Series Forecasting — Pure-Python Holt-Winters (Triple Exponential Smoothing).

No numpy/scipy/pandas — designed for Docker containers without ML libraries.
Uses Holt-Winters additive seasonality with damped trend for mood prediction.

v5.0.0 — PilotSuite Styx
"""
from __future__ import annotations

import logging
import math
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MOOD_DB_PATH = os.environ.get("COPILOT_MOOD_DB", "/data/mood_history.db")


class HoltWintersForecaster:
    """Pure-Python Holt-Winters triple exponential smoothing.

    Supports additive seasonality with configurable season period
    (hourly=24, daily=7).  All math is stdlib only — no numpy required.

    Parameters
    ----------
    alpha : float
        Level smoothing factor (0 < alpha < 1).
    beta : float
        Trend smoothing factor (0 < beta < 1).
    gamma : float
        Seasonal smoothing factor (0 < gamma < 1).
    season_length : int
        Number of periods in one season (e.g. 24 for hourly data).
    damped : bool
        If True, apply trend damping to prevent runaway forecasts.
    phi : float
        Trend damping factor (0 < phi <= 1).  Only used when damped=True.
    """

    def __init__(
        self,
        alpha: float = 0.3,
        beta: float = 0.1,
        gamma: float = 0.15,
        season_length: int = 24,
        damped: bool = True,
        phi: float = 0.95,
    ):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.season_length = season_length
        self.damped = damped
        self.phi = phi

        # Fitted state
        self._level: float = 0.0
        self._trend: float = 0.0
        self._seasonal: List[float] = []
        self._rmse: float = 0.0
        self._fitted = False
        self._n_obs: int = 0

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(self, data: List[float]) -> "HoltWintersForecaster":
        """Fit the model on historical time series data.

        Parameters
        ----------
        data : list[float]
            Evenly-spaced time series values.
            Must have len >= 2 * season_length.

        Returns
        -------
        self
            For method chaining.

        Raises
        ------
        ValueError
            If data is too short for the given season_length.
        """
        n = len(data)
        s = self.season_length

        if n < 2 * s:
            raise ValueError(
                f"Insufficient data: need >= {2 * s} observations "
                f"(2 × season_length={s}), got {n}"
            )

        # Initialize components
        level, trend, seasonal = self._initialize_components(data)

        # Smooth pass
        fitted, levels, trends, seasonals = self._smooth(
            data, level, trend, seasonal
        )

        # Store final state
        self._level = levels[-1]
        self._trend = trends[-1]
        # Keep the last season_length seasonals
        self._seasonal = seasonals[-s:]
        self._n_obs = n

        # Compute RMSE for prediction intervals
        residuals = [data[i] - fitted[i] for i in range(n)]
        sse = sum(r * r for r in residuals)
        self._rmse = math.sqrt(sse / n) if n > 0 else 0.0

        self._fitted = True
        logger.debug(
            "HoltWinters fit: n=%d, level=%.4f, trend=%.4f, rmse=%.4f",
            n, self._level, self._trend, self._rmse,
        )
        return self

    def forecast(self, steps: int = 24) -> List[Dict[str, Any]]:
        """Forecast future values.

        Parameters
        ----------
        steps : int
            Number of periods ahead to forecast.

        Returns
        -------
        list[dict]
            Each dict: {"step": int, "value": float, "lower": float, "upper": float}
        """
        if not self._fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        results = []
        s = self.season_length

        for h in range(1, steps + 1):
            # Damped trend accumulation
            if self.damped:
                phi_sum = sum(self.phi ** i for i in range(1, h + 1))
            else:
                phi_sum = float(h)

            seasonal_idx = (h - 1) % s
            point = self._level + phi_sum * self._trend + self._seasonal[seasonal_idx]

            # Prediction interval: grows with sqrt(h)
            margin = 1.96 * self._rmse * math.sqrt(h)
            lower = point - margin
            upper = point + margin

            # Clamp to [0, 1] for mood metrics
            point = max(0.0, min(1.0, point))
            lower = max(0.0, min(1.0, lower))
            upper = max(0.0, min(1.0, upper))

            results.append({
                "step": h,
                "value": round(point, 4),
                "lower": round(lower, 4),
                "upper": round(upper, 4),
            })

        return results

    def _initialize_components(
        self, data: List[float]
    ) -> Tuple[float, float, List[float]]:
        """Initialize level, trend, and seasonal components.

        Uses the first two full seasons:
        - level_0 = mean of first season
        - trend_0 = (mean_season2 - mean_season1) / season_length
        - seasonal_0[i] = data[i] - level_0 (additive)
        """
        s = self.season_length

        # Mean of first season
        mean_s1 = sum(data[:s]) / s
        # Mean of second season
        mean_s2 = sum(data[s : 2 * s]) / s

        level = mean_s1
        trend = (mean_s2 - mean_s1) / s

        # Initial seasonal components from first season
        seasonal = [data[i] - level for i in range(s)]

        return level, trend, seasonal

    def _smooth(
        self,
        data: List[float],
        level: float,
        trend: float,
        seasonal: List[float],
    ) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Run the Holt-Winters smoothing pass.

        Returns (fitted_values, levels, trends, seasonals_flat).
        """
        n = len(data)
        s = self.season_length
        a, b, g = self.alpha, self.beta, self.gamma
        phi = self.phi if self.damped else 1.0

        fitted = []
        levels = []
        trends = []
        all_seasonal = list(seasonal)  # Will grow as we process data

        for t in range(n):
            si = t % s
            y = data[t]

            if t == 0:
                # Use initialization values for first point
                fit_val = level + phi * trend + all_seasonal[si]
            else:
                fit_val = levels[-1] + phi * trends[-1] + all_seasonal[si]

            fitted.append(fit_val)

            # Update level
            new_level = a * (y - all_seasonal[si]) + (1 - a) * (level + phi * trend)

            # Update trend
            new_trend = b * (new_level - level) + (1 - b) * phi * trend

            # Update seasonal
            new_seasonal = g * (y - new_level) + (1 - g) * all_seasonal[si]

            # Store
            levels.append(new_level)
            trends.append(new_trend)

            # Update the seasonal component for this index
            if t < s:
                all_seasonal[si] = new_seasonal
            else:
                all_seasonal.append(new_seasonal)

            level = new_level
            trend = new_trend

        return fitted, levels, trends, all_seasonal


class MoodTimeSeriesForecaster:
    """High-level forecaster for mood metrics from SQLite history.

    Wraps HoltWintersForecaster with data loading, missing-value
    interpolation, and multi-metric (comfort/frugality/joy) forecasting.
    """

    METRICS = ("comfort", "frugality", "joy")

    def __init__(
        self,
        db_path: str | None = None,
        season_length: int = 24,
    ):
        self._db_path = db_path or MOOD_DB_PATH
        self._season_length = season_length
        self._lock = threading.Lock()
        # zone_id -> {metric_name: HoltWintersForecaster}
        self._models: Dict[str, Dict[str, HoltWintersForecaster]] = {}

    def fit_zone(self, zone_id: str, hours: int = 168) -> Dict[str, Any]:
        """Load mood history for a zone and fit models for each metric.

        Parameters
        ----------
        zone_id : str
            Zone identifier.
        hours : int
            How many hours of history to use (default 7 days = 168h).

        Returns
        -------
        dict
            Fit status per metric.
        """
        result: Dict[str, Any] = {"metrics": {}}
        models: Dict[str, HoltWintersForecaster] = {}

        for metric in self.METRICS:
            try:
                ts = self._load_timeseries(zone_id, metric, hours)
                if len(ts) < 2 * self._season_length:
                    result["metrics"][metric] = {
                        "status": "insufficient_data",
                        "samples": len(ts),
                        "required": 2 * self._season_length,
                    }
                    continue

                model = HoltWintersForecaster(
                    season_length=self._season_length
                )
                model.fit(ts)
                models[metric] = model
                result["metrics"][metric] = {
                    "status": "fitted",
                    "samples": len(ts),
                    "rmse": round(model._rmse, 4),
                }
            except Exception as exc:
                logger.error(
                    "Failed to fit %s for zone %s: %s",
                    metric, zone_id, exc, exc_info=True,
                )
                result["metrics"][metric] = {
                    "status": "error",
                    "error": str(exc),
                }

        with self._lock:
            self._models[zone_id] = models

        fitted_count = sum(
            1 for m in result["metrics"].values()
            if m.get("status") == "fitted"
        )
        result["fitted_metrics"] = fitted_count
        result["season_length"] = self._season_length
        logger.info(
            "Fitted %d/%d metrics for zone %s",
            fitted_count, len(self.METRICS), zone_id,
        )
        return result

    def forecast_zone(
        self, zone_id: str, steps: int = 24
    ) -> Dict[str, Any]:
        """Forecast mood metrics for a zone.

        Parameters
        ----------
        zone_id : str
            Zone identifier.
        steps : int
            Number of periods (hours) to forecast.

        Returns
        -------
        dict
            Forecasted values for each fitted metric.
        """
        with self._lock:
            models = self._models.get(zone_id)

        if not models:
            raise ValueError(
                f"No models fitted for zone '{zone_id}'. "
                f"Call fit_zone('{zone_id}') first."
            )

        metrics: Dict[str, Any] = {}
        for metric_name, model in models.items():
            try:
                metrics[metric_name] = model.forecast(steps)
            except Exception as exc:
                logger.error(
                    "Forecast failed for %s/%s: %s",
                    zone_id, metric_name, exc,
                )
                metrics[metric_name] = {"error": str(exc)}

        return {
            "zone_id": zone_id,
            "forecasted_at": datetime.now(timezone.utc).isoformat(),
            "steps": steps,
            "metrics": metrics,
            "season_length": self._season_length,
            "method": "holt_winters_additive_damped",
        }

    def _load_timeseries(
        self, zone_id: str, metric: str, hours: int
    ) -> List[float]:
        """Load evenly-spaced hourly time series from SQLite.

        Reads raw mood_snapshots, buckets by hour, fills gaps with
        linear interpolation.
        """
        cutoff = time.time() - (hours * 3600)

        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                f"SELECT timestamp, {metric} FROM mood_snapshots "
                "WHERE zone_id = ? AND timestamp > ? "
                "ORDER BY timestamp ASC",
                (zone_id, cutoff),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return []

        # Bucket into hourly bins
        buckets: Dict[int, List[float]] = {}
        for ts, val in rows:
            hour_key = int(ts) // 3600
            if hour_key not in buckets:
                buckets[hour_key] = []
            buckets[hour_key].append(val)

        if not buckets:
            return []

        # Build continuous hourly series
        min_hour = min(buckets.keys())
        max_hour = max(buckets.keys())
        sparse: List[Optional[float]] = []
        for h in range(min_hour, max_hour + 1):
            vals = buckets.get(h)
            if vals:
                sparse.append(sum(vals) / len(vals))
            else:
                sparse.append(None)

        # Interpolate gaps
        return self._interpolate_gaps(sparse)

    @staticmethod
    def _interpolate_gaps(data: List[Optional[float]]) -> List[float]:
        """Fill None gaps using linear interpolation between neighbors."""
        n = len(data)
        if n == 0:
            return []

        result = list(data)

        # Forward-fill leading Nones
        first_valid = None
        for i in range(n):
            if result[i] is not None:
                first_valid = i
                break

        if first_valid is None:
            return [0.5] * n  # All None — return neutral

        # Fill leading Nones
        for i in range(first_valid):
            result[i] = result[first_valid]

        # Fill trailing Nones
        last_valid = first_valid
        for i in range(n - 1, -1, -1):
            if result[i] is not None:
                last_valid = i
                break
        for i in range(last_valid + 1, n):
            result[i] = result[last_valid]

        # Linear interpolation for interior gaps
        i = 0
        while i < n:
            if result[i] is None:
                # Find the next non-None
                j = i + 1
                while j < n and result[j] is None:
                    j += 1
                # Interpolate between i-1 and j
                left = result[i - 1]
                right = result[j] if j < n else left
                gap_len = j - i + 1
                for k in range(i, min(j, n)):
                    t = (k - i + 1) / gap_len
                    result[k] = left * (1 - t) + right * t
            i += 1

        return [v if v is not None else 0.5 for v in result]
