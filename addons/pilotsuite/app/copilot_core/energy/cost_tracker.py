"""Energy Cost Tracker — Daily/weekly/monthly cost history (v5.10.0).

Tracks energy consumption costs over time with:
- Daily cost recording from consumption + pricing data
- Rolling averages (7-day, 30-day)
- Monthly budget tracking with overspend alerts
- Period comparison (this week vs last week, this month vs last month)
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

MAX_DAILY_HISTORY = 365  # 1 year of daily records


@dataclass
class DailyCost:
    """One day's energy cost record."""

    date: str  # YYYY-MM-DD
    consumption_kwh: float
    production_kwh: float
    net_consumption_kwh: float  # consumption - production
    avg_price_eur_kwh: float
    total_cost_eur: float
    savings_from_solar_eur: float


@dataclass
class CostSummary:
    """Aggregated cost summary for a period."""

    period: str  # "daily", "weekly", "monthly"
    start_date: str
    end_date: str
    total_cost_eur: float
    total_consumption_kwh: float
    total_production_kwh: float
    total_savings_eur: float
    avg_daily_cost_eur: float
    days_count: int


@dataclass
class BudgetStatus:
    """Monthly budget tracking."""

    month: str  # YYYY-MM
    budget_eur: float
    spent_eur: float
    remaining_eur: float
    percent_used: float
    projected_total_eur: float
    on_track: bool


class EnergyCostTracker:
    """Track and analyze energy costs over time."""

    def __init__(self, monthly_budget_eur: float = 100.0):
        self._lock = threading.Lock()
        self._daily_records: deque[DailyCost] = deque(maxlen=MAX_DAILY_HISTORY)
        self._monthly_budget = monthly_budget_eur
        logger.info("EnergyCostTracker initialized (budget=%.2f EUR/month)", monthly_budget_eur)

    def record_day(
        self,
        consumption_kwh: float,
        production_kwh: float,
        avg_price_eur_kwh: float,
        record_date: date | None = None,
    ) -> DailyCost:
        """Record a day's energy cost."""
        d = record_date or date.today()
        net = max(0.0, consumption_kwh - production_kwh)
        cost = net * avg_price_eur_kwh
        solar_savings = min(consumption_kwh, production_kwh) * avg_price_eur_kwh

        record = DailyCost(
            date=d.isoformat(),
            consumption_kwh=round(consumption_kwh, 2),
            production_kwh=round(production_kwh, 2),
            net_consumption_kwh=round(net, 2),
            avg_price_eur_kwh=round(avg_price_eur_kwh, 4),
            total_cost_eur=round(cost, 4),
            savings_from_solar_eur=round(solar_savings, 4),
        )

        with self._lock:
            # Replace existing record for same date or append
            existing_idx = None
            for i, r in enumerate(self._daily_records):
                if r.date == record.date:
                    existing_idx = i
                    break

            if existing_idx is not None:
                self._daily_records[existing_idx] = record
            else:
                self._daily_records.append(record)

        return record

    def get_daily_history(self, days: int = 30) -> list[dict[str, Any]]:
        """Get recent daily cost records."""
        with self._lock:
            records = list(self._daily_records)

        records.sort(key=lambda r: r.date, reverse=True)
        records = records[:days]

        return [
            {
                "date": r.date,
                "consumption_kwh": r.consumption_kwh,
                "production_kwh": r.production_kwh,
                "net_consumption_kwh": r.net_consumption_kwh,
                "cost_eur": r.total_cost_eur,
                "savings_eur": r.savings_from_solar_eur,
            }
            for r in records
        ]

    def get_summary(self, period: str = "weekly") -> CostSummary:
        """Get cost summary for a period.

        Parameters
        ----------
        period : str
            "daily" (today), "weekly" (last 7 days), "monthly" (last 30 days)
        """
        today = date.today()

        if period == "daily":
            start = today
            days = 1
        elif period == "weekly":
            start = today - timedelta(days=6)
            days = 7
        else:  # monthly
            start = today - timedelta(days=29)
            days = 30

        with self._lock:
            records = [
                r for r in self._daily_records
                if start.isoformat() <= r.date <= today.isoformat()
            ]

        total_cost = sum(r.total_cost_eur for r in records)
        total_consumption = sum(r.consumption_kwh for r in records)
        total_production = sum(r.production_kwh for r in records)
        total_savings = sum(r.savings_from_solar_eur for r in records)
        actual_days = max(1, len(records))

        return CostSummary(
            period=period,
            start_date=start.isoformat(),
            end_date=today.isoformat(),
            total_cost_eur=round(total_cost, 2),
            total_consumption_kwh=round(total_consumption, 2),
            total_production_kwh=round(total_production, 2),
            total_savings_eur=round(total_savings, 2),
            avg_daily_cost_eur=round(total_cost / actual_days, 2),
            days_count=actual_days,
        )

    def get_budget_status(self) -> BudgetStatus:
        """Get monthly budget tracking status."""
        today = date.today()
        month_str = today.strftime("%Y-%m")
        month_start = today.replace(day=1)

        with self._lock:
            month_records = [
                r for r in self._daily_records
                if r.date >= month_start.isoformat()
            ]

        spent = sum(r.total_cost_eur for r in month_records)
        remaining = self._monthly_budget - spent
        days_elapsed = max(1, (today - month_start).days + 1)

        # Project to end of month
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        days_in_month = (next_month - month_start).days
        daily_avg = spent / days_elapsed
        projected = daily_avg * days_in_month

        percent_used = (spent / self._monthly_budget * 100) if self._monthly_budget > 0 else 0

        return BudgetStatus(
            month=month_str,
            budget_eur=round(self._monthly_budget, 2),
            spent_eur=round(spent, 2),
            remaining_eur=round(remaining, 2),
            percent_used=round(percent_used, 1),
            projected_total_eur=round(projected, 2),
            on_track=projected <= self._monthly_budget,
        )

    def compare_periods(
        self, current_days: int = 7, offset_days: int = 7
    ) -> dict[str, Any]:
        """Compare current period with previous period.

        E.g., compare last 7 days with the 7 days before that.
        """
        today = date.today()
        current_start = today - timedelta(days=current_days - 1)
        prev_end = current_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=offset_days - 1)

        with self._lock:
            records = list(self._daily_records)

        current = [r for r in records if current_start.isoformat() <= r.date <= today.isoformat()]
        previous = [r for r in records if prev_start.isoformat() <= r.date <= prev_end.isoformat()]

        curr_cost = sum(r.total_cost_eur for r in current)
        prev_cost = sum(r.total_cost_eur for r in previous)
        curr_kwh = sum(r.consumption_kwh for r in current)
        prev_kwh = sum(r.consumption_kwh for r in previous)

        cost_diff = curr_cost - prev_cost
        cost_pct = ((cost_diff / prev_cost) * 100) if prev_cost > 0 else 0.0

        return {
            "current_period": {
                "start": current_start.isoformat(),
                "end": today.isoformat(),
                "cost_eur": round(curr_cost, 2),
                "consumption_kwh": round(curr_kwh, 2),
                "days": len(current),
            },
            "previous_period": {
                "start": prev_start.isoformat(),
                "end": prev_end.isoformat(),
                "cost_eur": round(prev_cost, 2),
                "consumption_kwh": round(prev_kwh, 2),
                "days": len(previous),
            },
            "difference_eur": round(cost_diff, 2),
            "change_percent": round(cost_pct, 1),
            "trend": "up" if cost_diff > 0.5 else ("down" if cost_diff < -0.5 else "stable"),
        }

    def get_rolling_average(self, window_days: int = 7) -> float:
        """Get rolling average daily cost."""
        today = date.today()
        start = (today - timedelta(days=window_days - 1)).isoformat()

        with self._lock:
            records = [r for r in self._daily_records if r.date >= start]

        if not records:
            return 0.0

        return round(sum(r.total_cost_eur for r in records) / len(records), 2)
