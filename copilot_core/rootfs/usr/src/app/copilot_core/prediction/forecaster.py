"""
Forecaster -- Predict arrival times and patterns.

Uses simple statistical methods (moving averages, time-of-day weighting)
rather than heavy ML frameworks. Designed for edge/embedded deployment.
"""
from __future__ import annotations

import logging
import math
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("PREDICTIONS_DB", "/data/predictions.db")


class ArrivalForecaster:
    """Predict arrival times for household members.

    Records historical arrivals and uses a time-weighted average of
    same-weekday, same-hour arrivals to generate predictions.  No heavy
    ML frameworks are needed -- just basic statistics.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        logger.info("ArrivalForecaster initialized at %s", self._db_path)

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS arrivals (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        person_id  TEXT NOT NULL,
                        arrived_at TEXT NOT NULL,
                        weekday    INTEGER NOT NULL,
                        hour       INTEGER NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_arrivals_person
                        ON arrivals(person_id);
                    CREATE INDEX IF NOT EXISTS idx_arrivals_weekday
                        ON arrivals(weekday);
                """)
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_arrival(
        self, person_id: str, timestamp: Optional[str] = None
    ) -> None:
        """Record a new arrival event.

        Parameters
        ----------
        person_id : str
            HA person entity id (e.g. ``person.alice``).
        timestamp : str, optional
            ISO-8601 timestamp.  Defaults to *now* (UTC).
        """
        if timestamp is None:
            dt = datetime.now(timezone.utc)
        else:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        arrived_iso = dt.isoformat()
        weekday = dt.weekday()  # 0 = Monday
        hour = dt.hour

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT INTO arrivals (person_id, arrived_at, weekday, hour) "
                    "VALUES (?, ?, ?, ?)",
                    (person_id, arrived_iso, weekday, hour),
                )
                conn.commit()
                logger.debug(
                    "Arrival recorded: %s at %s (wd=%d h=%d)",
                    person_id, arrived_iso, weekday, hour,
                )
            finally:
                conn.close()

    def predict_arrival(
        self, person_id: str, horizon_minutes: int = 120
    ) -> Dict[str, Any]:
        """Predict the next arrival for *person_id*.

        Returns
        -------
        dict
            ``predicted_arrival`` (ISO), ``confidence``, ``method``.
        """
        now = datetime.now(timezone.utc)
        current_weekday = now.weekday()
        current_hour = now.hour

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT arrived_at, weekday, hour FROM arrivals "
                    "WHERE person_id = ? ORDER BY arrived_at DESC LIMIT 200",
                    (person_id,),
                ).fetchall()
            finally:
                conn.close()

        if not rows:
            return {
                "person_id": person_id,
                "predicted_arrival": None,
                "confidence": 0.0,
                "method": "no_data",
            }

        offset_minutes = self._time_weighted_average(
            rows, current_weekday, current_hour
        )
        predicted = now + timedelta(minutes=offset_minutes)
        # Clamp to horizon
        horizon_end = now + timedelta(minutes=horizon_minutes)
        if predicted > horizon_end:
            predicted = horizon_end

        confidence = min(1.0, len(rows) / 30.0)  # more data -> higher confidence

        return {
            "person_id": person_id,
            "predicted_arrival": predicted.isoformat(),
            "confidence": round(confidence, 4),
            "method": "time_weighted_average",
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _time_weighted_average(
        self,
        arrivals: List[tuple],
        current_weekday: int,
        current_hour: int,
    ) -> float:
        """Compute a weighted average offset (in minutes from now).

        Same-weekday arrivals receive higher weight; same-hour arrivals
        get an additional boost.  Recent arrivals are weighted more.
        """
        weighted_sum = 0.0
        weight_total = 0.0

        now = datetime.now(timezone.utc)

        for arrived_at_str, weekday, hour in arrivals:
            dt = datetime.fromisoformat(
                arrived_at_str.replace("Z", "+00:00")
            )
            age_days = max((now - dt).total_seconds() / 86400.0, 0.001)

            # Recency weight: exponential decay (half-life 14 days)
            recency = math.exp(-0.693 * age_days / 14.0)

            # Weekday similarity weight
            weekday_w = 2.0 if weekday == current_weekday else 0.5

            # Hour similarity weight
            hour_diff = abs(hour - current_hour)
            hour_w = max(0.2, 1.0 - hour_diff * 0.15)

            weight = recency * weekday_w * hour_w

            # Offset = how many minutes after this hour the arrival was
            minutes_of_day = hour * 60 + dt.minute
            current_minutes = current_hour * 60 + now.minute
            offset = minutes_of_day - current_minutes
            if offset < 0:
                offset += 1440  # wrap to next day

            weighted_sum += offset * weight
            weight_total += weight

        if weight_total == 0:
            return 60.0  # fallback: 1 hour

        return weighted_sum / weight_total
