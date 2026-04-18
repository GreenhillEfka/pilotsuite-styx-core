"""Energy Report Generator — Structured energy reports (v5.13.0).

Generates daily, weekly, and monthly energy reports with:
- Consumption vs production breakdown
- Cost analysis with comparison to previous period
- Solar self-consumption ratio
- Device-level insights from fingerprints
- Optimization recommendations (German)
- Export as structured dict (JSON-serializable for HTML/PDF rendering)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Any, Optional


@dataclass
class ConsumptionBreakdown:
    """Consumption breakdown for a report period."""

    total_consumption_kwh: float
    total_production_kwh: float
    net_grid_kwh: float  # from grid
    self_consumed_kwh: float
    fed_in_kwh: float  # excess sold back
    self_consumption_ratio_pct: float
    autarky_ratio_pct: float  # % of consumption covered by own production


@dataclass
class CostBreakdown:
    """Cost breakdown for a report period."""

    gross_cost_eur: float  # without solar
    net_cost_eur: float  # actual cost after solar offset
    solar_savings_eur: float
    feed_in_revenue_eur: float
    avg_price_eur_kwh: float
    cheapest_day: str
    most_expensive_day: str


@dataclass
class PeriodComparison:
    """Comparison to previous equivalent period."""

    consumption_change_pct: float
    cost_change_pct: float
    production_change_pct: float
    trend: str  # "improving", "stable", "worsening"
    summary_de: str  # German summary sentence


@dataclass
class Recommendation:
    """Single optimization recommendation."""

    category: str  # "scheduling", "solar", "consumption", "tariff"
    title_de: str
    description_de: str
    potential_savings_eur: float
    priority: int  # 1=high, 3=low


@dataclass
class EnergyReport:
    """Complete energy report."""

    report_id: str
    report_type: str  # "daily", "weekly", "monthly"
    period_start: str
    period_end: str
    generated_at: str
    consumption: dict
    costs: dict
    comparison: dict
    recommendations: list[dict]
    highlights: list[str]
    device_insights: list[dict]


# ── Constants ───────────────────────────────────────────────────────────────

FEED_IN_TARIFF_EUR_KWH = 0.082  # German EEG 2024 for <10 kWp
DEFAULT_GRID_PRICE_EUR_KWH = 0.30


class EnergyReportGenerator:
    """Generates structured energy reports."""

    def __init__(
        self,
        grid_price_eur_kwh: float = DEFAULT_GRID_PRICE_EUR_KWH,
        feed_in_tariff_eur_kwh: float = FEED_IN_TARIFF_EUR_KWH,
    ):
        self._grid_price = grid_price_eur_kwh
        self._feed_in = feed_in_tariff_eur_kwh
        self._daily_data: dict[str, dict] = {}

    # ── Data ingestion ──────────────────────────────────────────────────

    def add_daily_data(
        self,
        day: date,
        consumption_kwh: float,
        production_kwh: float,
        avg_price_eur_kwh: float | None = None,
        devices: list[dict] | None = None,
    ) -> None:
        """Add or update daily energy data.

        Parameters
        ----------
        devices : list of {device_name, kwh, runs} dicts (optional)
        """
        key = day.isoformat()
        self_consumed = min(consumption_kwh, production_kwh)
        net_grid = max(0, consumption_kwh - production_kwh)
        fed_in = max(0, production_kwh - consumption_kwh)
        price = avg_price_eur_kwh or self._grid_price

        self._daily_data[key] = {
            "date": key,
            "consumption_kwh": consumption_kwh,
            "production_kwh": production_kwh,
            "self_consumed_kwh": self_consumed,
            "net_grid_kwh": net_grid,
            "fed_in_kwh": fed_in,
            "avg_price_eur_kwh": price,
            "net_cost_eur": round(net_grid * price, 2),
            "gross_cost_eur": round(consumption_kwh * price, 2),
            "solar_savings_eur": round(self_consumed * price, 2),
            "feed_in_revenue_eur": round(fed_in * self._feed_in, 2),
            "devices": devices or [],
        }

    # ── Report generation ───────────────────────────────────────────────

    def generate_report(
        self,
        report_type: str = "weekly",
        end_date: date | None = None,
    ) -> EnergyReport:
        """Generate a structured energy report.

        Parameters
        ----------
        report_type : "daily", "weekly", "monthly"
        end_date : last day of report period (default today)
        """
        end = end_date or date.today()

        if report_type == "daily":
            start = end
            prev_start = end - timedelta(days=1)
            prev_end = end - timedelta(days=1)
        elif report_type == "weekly":
            start = end - timedelta(days=6)
            prev_start = start - timedelta(days=7)
            prev_end = start - timedelta(days=1)
        else:  # monthly
            start = end.replace(day=1)
            prev_month_end = start - timedelta(days=1)
            prev_start = prev_month_end.replace(day=1)
            prev_end = prev_month_end

        current_days = self._get_days(start, end)
        previous_days = self._get_days(prev_start, prev_end)

        consumption = self._build_consumption(current_days)
        costs = self._build_costs(current_days)
        comparison = self._build_comparison(current_days, previous_days)
        recommendations = self._build_recommendations(current_days, consumption, costs)
        highlights = self._build_highlights(consumption, costs, comparison, report_type)
        device_insights = self._build_device_insights(current_days)

        report_id = f"{report_type}_{end.isoformat()}_{datetime.now().strftime('%H%M%S')}"

        return EnergyReport(
            report_id=report_id,
            report_type=report_type,
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            generated_at=datetime.now().isoformat(),
            consumption=asdict(consumption),
            costs=asdict(costs),
            comparison=asdict(comparison),
            recommendations=[asdict(r) for r in recommendations],
            highlights=highlights,
            device_insights=device_insights,
        )

    def get_data_coverage(self) -> dict:
        """Return info about available data."""
        if not self._daily_data:
            return {"days": 0, "first_date": None, "last_date": None}
        dates = sorted(self._daily_data.keys())
        return {
            "days": len(dates),
            "first_date": dates[0],
            "last_date": dates[-1],
        }

    def generate_usage_pattern_summary(
        self,
        pattern_learner: Any,
        *,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        min_confidence: float = 0.0,
    ) -> dict:
        """Build the bounded D1 usage-pattern summary report shape."""
        end = window_end or datetime.now()
        start = window_start or (end - timedelta(days=7))
        if start > end:
            raise ValueError("window_start must be before or equal to window_end")

        if not hasattr(pattern_learner, "get_pattern_summaries"):
            raise TypeError("pattern_learner must expose get_pattern_summaries(...)")

        pattern_summaries = self._get_usage_pattern_window_summaries(
            min_confidence=min_confidence,
            window_start=start,
            window_end=end,
            pattern_learner=pattern_learner,
        )

        comparison_end = start
        comparison_start = comparison_end - (end - start)
        comparison_summaries = self._get_usage_pattern_window_summaries(
            min_confidence=min_confidence,
            window_start=comparison_start,
            window_end=comparison_end,
            pattern_learner=pattern_learner,
        )

        comparison_by_id = {
            summary["pattern_id"]: summary for summary in comparison_summaries
        }

        patterns = [
            self._build_usage_pattern_summary_item(
                summary,
                comparison_by_id.get(summary["pattern_id"]),
            )
            for summary in pattern_summaries
        ]

        return {
            "status": "ok",
            "window": {
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
            "comparison_window": {
                "from": comparison_start.isoformat(),
                "to": comparison_end.isoformat(),
            },
            "patterns": patterns,
            "impact": self._build_usage_pattern_impact(pattern_summaries),
            "drift": self._build_usage_pattern_drift(pattern_summaries, comparison_summaries),
            "recommendations": self._build_usage_pattern_recommendations(
                pattern_summaries,
                comparison_summaries,
            ),
        }

    def export_usage_pattern_summary(
        self,
        pattern_learner: Any,
        *,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Return the canonical D1/D2/D3 usage-pattern payload unchanged for API export."""
        return self.generate_usage_pattern_summary(
            pattern_learner,
            window_start=window_start,
            window_end=window_end,
            min_confidence=min_confidence,
        )

    # ── Internal builders ───────────────────────────────────────────────

    @staticmethod
    def _get_usage_pattern_window_summaries(
        pattern_learner: Any,
        *,
        window_start: datetime,
        window_end: datetime,
        min_confidence: float,
    ) -> list[dict[str, Any]]:
        """Read windowed pattern summaries when the learner exposes them."""
        if hasattr(pattern_learner, "get_pattern_window_summaries"):
            return pattern_learner.get_pattern_window_summaries(
                min_confidence=min_confidence,
                window_start=window_start,
                window_end=window_end,
            )

        return pattern_learner.get_pattern_summaries(
            min_confidence=min_confidence,
            window_start=window_start,
            window_end=window_end,
        )

    @staticmethod
    def _build_usage_pattern_summary_item(
        current_summary: dict[str, Any],
        previous_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build one D2 pattern item with bounded comparison fields."""
        current_frequency = int(current_summary.get("occurrence_count", 0))
        previous_frequency = int(previous_summary.get("occurrence_count", 0)) if previous_summary else 0

        return {
            "pattern_id": current_summary["pattern_id"],
            "category": current_summary.get("category", "automation"),
            "zone": current_summary.get("zone"),
            "frequency": current_frequency,
            "previous_frequency": previous_frequency,
            "frequency_delta": current_frequency - previous_frequency,
            "confidence": round(float(current_summary.get("confidence", 0.0)), 3),
            "last_seen": current_summary.get("last_occurrence"),
            "trend": EnergyReportGenerator._classify_usage_pattern_trend(
                current_summary,
                previous_summary,
            ),
        }

    @staticmethod
    def _classify_usage_pattern_trend(
        current_summary: dict[str, Any],
        previous_summary: dict[str, Any] | None,
    ) -> str:
        """Classify one bounded trend signal without overclaiming sparse data."""
        current_source = current_summary.get("window_metrics_source")
        previous_source = previous_summary.get("window_metrics_source") if previous_summary else None

        if current_source != "observations":
            return "stable"
        if previous_summary and previous_source not in {None, "observations"}:
            return "stable"

        current_frequency = int(current_summary.get("occurrence_count", 0))
        previous_frequency = int(previous_summary.get("occurrence_count", 0)) if previous_summary else 0

        if previous_frequency == 0:
            return "rising"

        change_ratio = (current_frequency - previous_frequency) / max(previous_frequency, 1)
        if change_ratio >= 0.25:
            return "rising"
        if change_ratio <= -0.25:
            return "falling"
        return "stable"

    @staticmethod
    def _build_usage_pattern_drift(
        current_summaries: list[dict[str, Any]],
        previous_summaries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the bounded D2 drift summary over two adjacent windows."""
        current_by_id = {summary["pattern_id"]: summary for summary in current_summaries}
        previous_by_id = {summary["pattern_id"]: summary for summary in previous_summaries}

        shared_ids = sorted(set(current_by_id) & set(previous_by_id))
        rising = 0
        stable = 0
        falling = 0

        for pattern_id in shared_ids:
            trend = EnergyReportGenerator._classify_usage_pattern_trend(
                current_by_id[pattern_id],
                previous_by_id[pattern_id],
            )
            if trend == "rising":
                rising += 1
            elif trend == "falling":
                falling += 1
            else:
                stable += 1

        new_patterns = [
            {
                "pattern_id": summary["pattern_id"],
                "category": summary.get("category", "automation"),
                "zone": summary.get("zone"),
                "frequency": int(summary.get("occurrence_count", 0)),
                "last_seen": summary.get("last_occurrence"),
            }
            for summary in current_summaries
            if summary.get("window_metrics_source") == "observations"
            and summary["pattern_id"] not in previous_by_id
        ]

        fading_patterns = [
            {
                "pattern_id": summary["pattern_id"],
                "category": summary.get("category", "automation"),
                "zone": summary.get("zone"),
                "previous_frequency": int(summary.get("occurrence_count", 0)),
                "last_seen": summary.get("last_occurrence"),
            }
            for summary in previous_summaries
            if summary.get("window_metrics_source") == "observations"
            and summary["pattern_id"] not in current_by_id
        ]

        return {
            "summary": {
                "new_patterns": len(new_patterns),
                "fading_patterns": len(fading_patterns),
                "rising_patterns": rising,
                "stable_patterns": stable,
                "falling_patterns": falling,
            },
            "new_patterns": new_patterns,
            "fading_patterns": fading_patterns,
        }

    def _build_usage_pattern_impact(self, pattern_summaries: list[dict[str, Any]]) -> dict[str, float]:
        """Aggregate bounded impact estimates from pattern summaries."""
        estimated_energy = 0.0
        estimated_cost = 0.0

        for summary in pattern_summaries:
            energy = self._coerce_non_negative_float(summary.get("estimated_energy_impact_kwh"))
            cost = self._coerce_non_negative_float(summary.get("estimated_cost_impact_eur"))
            if cost == 0.0 and energy > 0.0:
                cost = round(energy * self._grid_price, 2)

            estimated_energy += energy
            estimated_cost += cost

        return {
            "estimated_cost_impact_eur": round(estimated_cost, 2),
            "estimated_energy_impact_kwh": round(estimated_energy, 3),
        }

    def _build_usage_pattern_recommendations(
        self,
        current_summaries: list[dict[str, Any]],
        previous_summaries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build one bounded D3 recommendation layer with conservative explainability."""
        current_by_id = {summary["pattern_id"]: summary for summary in current_summaries}
        previous_by_id = {summary["pattern_id"]: summary for summary in previous_summaries}

        recommendations: list[dict[str, Any]] = []
        emitted_keys: set[tuple[str, str, str]] = set()

        ranked_current = sorted(
            current_summaries,
            key=lambda summary: (
                -self._usage_pattern_priority_seed(summary),
                -self._usage_pattern_benefit_cost(summary),
                -self._usage_pattern_benefit_energy(summary),
                -float(summary.get("confidence", 0.0)),
                str(summary.get("pattern_id", "")),
            ),
        )

        for summary in ranked_current:
            recommendation = self._build_usage_pattern_current_recommendation(
                summary,
                previous_by_id.get(summary["pattern_id"]),
                emitted_keys=emitted_keys,
            )
            if recommendation:
                recommendations.append(recommendation)

        ranked_previous = sorted(
            previous_summaries,
            key=lambda summary: (
                -int(summary.get("occurrence_count", 0)),
                -float(summary.get("confidence", 0.0)),
                str(summary.get("pattern_id", "")),
            ),
        )

        for summary in ranked_previous:
            if summary["pattern_id"] in current_by_id:
                continue
            recommendation = self._build_usage_pattern_fading_recommendation(
                summary,
                emitted_keys=emitted_keys,
            )
            if recommendation:
                recommendations.append(recommendation)

        recommendations.sort(
            key=lambda item: (
                int(item["priority"]),
                -float(item["expected_benefit"]["estimated_cost_impact_eur"]),
                -float(item["expected_benefit"]["estimated_energy_impact_kwh"]),
                -float(item["confidence"]),
                str(item["recommendation_id"]),
            )
        )
        return recommendations[:3]

    def _build_usage_pattern_current_recommendation(
        self,
        current_summary: dict[str, Any],
        previous_summary: dict[str, Any] | None,
        *,
        emitted_keys: set[tuple[str, str, str]],
    ) -> dict[str, Any] | None:
        """Build a recommendation for a current-window pattern when evidence is strong enough."""
        if current_summary.get("window_metrics_source") != "observations":
            return None

        confidence = round(float(current_summary.get("confidence", 0.0)), 3)
        current_frequency = int(current_summary.get("occurrence_count", 0))
        if confidence < 0.65 or current_frequency < 2:
            return None

        previous_frequency = int(previous_summary.get("occurrence_count", 0)) if previous_summary else 0
        trend = self._classify_usage_pattern_trend(current_summary, previous_summary)
        category = str(current_summary.get("category", "automation"))
        zone = str(current_summary.get("zone") or "unknown")
        benefit = self._build_usage_pattern_expected_benefit(current_summary)
        pattern_id = str(current_summary["pattern_id"])

        if trend == "rising" and (
            benefit["estimated_cost_impact_eur"] > 0.0
            or benefit["estimated_energy_impact_kwh"] > 0.0
            or category == "energy"
        ):
            family = "optimize_rising_usage"
            dedupe_key = (family, category, zone)
            if dedupe_key in emitted_keys:
                return None
            emitted_keys.add(dedupe_key)

            return {
                "recommendation_id": f"{pattern_id}:optimize_rising_usage",
                "title": self._format_usage_pattern_title("Tune rising", category, zone),
                "reason": (
                    f"{category.capitalize()} usage changed from {previous_frequency} to "
                    f"{current_frequency} events in the current window."
                ),
                "why_now": (
                    f"This pattern is rising now and was last seen at "
                    f"{current_summary.get('last_occurrence')} with {confidence:.2f} confidence."
                ),
                "expected_benefit": benefit,
                "confidence": confidence,
                "priority": self._classify_usage_pattern_priority(benefit),
                "action_type": self._classify_usage_pattern_action_type(category),
                "explainability": {
                    "kind": family,
                    "pattern_ids": [pattern_id],
                    "evidence": {
                        "category": category,
                        "zone": current_summary.get("zone"),
                        "current_frequency": current_frequency,
                        "previous_frequency": previous_frequency,
                        "frequency_delta": current_frequency - previous_frequency,
                        "trend": trend,
                        "last_seen": current_summary.get("last_occurrence"),
                        "window_metrics_source": current_summary.get("window_metrics_source"),
                    },
                },
            }

        if previous_summary is None and confidence >= 0.75:
            family = "review_new_pattern"
            dedupe_key = (family, category, zone)
            if dedupe_key in emitted_keys:
                return None
            emitted_keys.add(dedupe_key)

            return {
                "recommendation_id": f"{pattern_id}:review_new_pattern",
                "title": self._format_usage_pattern_title("Review new", category, zone),
                "reason": (
                    f"{category.capitalize()} usage appeared {current_frequency} times in the current "
                    "window and was absent in the previous window."
                ),
                "why_now": (
                    f"This is a new observed pattern with {confidence:.2f} confidence, so it is a good "
                    "moment to confirm whether it should become an automation or reporting rule."
                ),
                "expected_benefit": benefit,
                "confidence": confidence,
                "priority": 2,
                "action_type": "manual",
                "explainability": {
                    "kind": family,
                    "pattern_ids": [pattern_id],
                    "evidence": {
                        "category": category,
                        "zone": current_summary.get("zone"),
                        "current_frequency": current_frequency,
                        "previous_frequency": 0,
                        "frequency_delta": current_frequency,
                        "trend": trend,
                        "last_seen": current_summary.get("last_occurrence"),
                        "window_metrics_source": current_summary.get("window_metrics_source"),
                    },
                },
            }

        return None

    def _build_usage_pattern_fading_recommendation(
        self,
        previous_summary: dict[str, Any],
        *,
        emitted_keys: set[tuple[str, str, str]],
    ) -> dict[str, Any] | None:
        """Build one bounded fading-pattern review recommendation."""
        if previous_summary.get("window_metrics_source") != "observations":
            return None

        confidence = round(float(previous_summary.get("confidence", 0.0)), 3)
        previous_frequency = int(previous_summary.get("occurrence_count", 0))
        if confidence < 0.65 or previous_frequency < 2:
            return None

        category = str(previous_summary.get("category", "automation"))
        zone = str(previous_summary.get("zone") or "unknown")
        family = "review_fading_pattern"
        dedupe_key = (family, category, zone)
        if dedupe_key in emitted_keys:
            return None
        emitted_keys.add(dedupe_key)

        pattern_id = str(previous_summary["pattern_id"])
        return {
            "recommendation_id": f"{pattern_id}:review_fading_pattern",
            "title": self._format_usage_pattern_title("Review fading", category, zone),
            "reason": (
                f"{category.capitalize()} usage was seen {previous_frequency} times in the previous "
                "window and did not reappear in the current one."
            ),
            "why_now": (
                "A disappearing pattern can mean an obsolete routine, seasonal drift, or a broken "
                "automation, so it is worth validating before it silently rots."
            ),
            "expected_benefit": {
                "estimated_cost_impact_eur": 0.0,
                "estimated_energy_impact_kwh": 0.0,
            },
            "confidence": confidence,
            "priority": 3,
            "action_type": "manual",
            "explainability": {
                "kind": family,
                "pattern_ids": [pattern_id],
                "evidence": {
                    "category": category,
                    "zone": previous_summary.get("zone"),
                    "current_frequency": 0,
                    "previous_frequency": previous_frequency,
                    "frequency_delta": -previous_frequency,
                    "trend": "falling",
                    "last_seen": previous_summary.get("last_occurrence"),
                    "window_metrics_source": previous_summary.get("window_metrics_source"),
                },
            },
        }

    def _build_usage_pattern_expected_benefit(self, summary: dict[str, Any]) -> dict[str, float]:
        """Normalize the benefit estimate for a single recommendation candidate."""
        energy = self._coerce_non_negative_float(summary.get("estimated_energy_impact_kwh"))
        cost = self._coerce_non_negative_float(summary.get("estimated_cost_impact_eur"))
        if cost == 0.0 and energy > 0.0:
            cost = round(energy * self._grid_price, 2)
        return {
            "estimated_cost_impact_eur": round(cost, 2),
            "estimated_energy_impact_kwh": round(energy, 3),
        }

    @staticmethod
    def _format_usage_pattern_title(prefix: str, category: str, zone: str) -> str:
        """Create a short human-readable title for one pattern recommendation."""
        base = f"{prefix} {category} routine"
        if zone == "unknown":
            return base
        return f"{base} in {zone}"

    @staticmethod
    def _classify_usage_pattern_action_type(category: str) -> str:
        """Pick the bounded action type for a recommendation family."""
        if category in {"energy", "media", "automation"}:
            return "schedule"
        return "manual"

    @staticmethod
    def _classify_usage_pattern_priority(benefit: dict[str, float]) -> int:
        """Turn estimated benefit into a stable bounded priority."""
        if (
            float(benefit["estimated_cost_impact_eur"]) >= 1.0
            or float(benefit["estimated_energy_impact_kwh"]) >= 2.0
        ):
            return 1
        return 2

    def _usage_pattern_priority_seed(self, summary: dict[str, Any]) -> float:
        """Return a ranking seed so higher-signal patterns win the bounded cooldown slots."""
        benefit = self._build_usage_pattern_expected_benefit(summary)
        return (
            self._usage_pattern_benefit_cost(summary) * 10
            + self._usage_pattern_benefit_energy(summary)
            + float(summary.get("confidence", 0.0))
            + int(summary.get("occurrence_count", 0))
        )

    def _usage_pattern_benefit_cost(self, summary: dict[str, Any]) -> float:
        """Return the estimated cost benefit for ranking purposes."""
        return self._build_usage_pattern_expected_benefit(summary)["estimated_cost_impact_eur"]

    def _usage_pattern_benefit_energy(self, summary: dict[str, Any]) -> float:
        """Return the estimated energy benefit for ranking purposes."""
        return self._build_usage_pattern_expected_benefit(summary)["estimated_energy_impact_kwh"]

    @staticmethod
    def _coerce_non_negative_float(value: Any) -> float:
        """Return a non-negative float, otherwise ``0.0``."""
        if isinstance(value, bool):
            return 0.0
        if not isinstance(value, (int, float)):
            return 0.0
        return round(max(0.0, float(value)), 3)

    def _get_days(self, start: date, end: date) -> list[dict]:
        """Get daily data for a date range."""
        result = []
        d = start
        while d <= end:
            data = self._daily_data.get(d.isoformat())
            if data:
                result.append(data)
            d += timedelta(days=1)
        return result

    @staticmethod
    def _build_consumption(days: list[dict]) -> ConsumptionBreakdown:
        if not days:
            return ConsumptionBreakdown(0, 0, 0, 0, 0, 0, 0)

        total_c = sum(d["consumption_kwh"] for d in days)
        total_p = sum(d["production_kwh"] for d in days)
        total_sc = sum(d["self_consumed_kwh"] for d in days)
        total_grid = sum(d["net_grid_kwh"] for d in days)
        total_fi = sum(d["fed_in_kwh"] for d in days)

        sc_ratio = round(total_sc / total_p * 100, 1) if total_p > 0 else 0.0
        autarky = round(total_sc / total_c * 100, 1) if total_c > 0 else 0.0

        return ConsumptionBreakdown(
            total_consumption_kwh=round(total_c, 2),
            total_production_kwh=round(total_p, 2),
            net_grid_kwh=round(total_grid, 2),
            self_consumed_kwh=round(total_sc, 2),
            fed_in_kwh=round(total_fi, 2),
            self_consumption_ratio_pct=sc_ratio,
            autarky_ratio_pct=autarky,
        )

    @staticmethod
    def _build_costs(days: list[dict]) -> CostBreakdown:
        if not days:
            return CostBreakdown(0, 0, 0, 0, 0, "", "")

        gross = sum(d["gross_cost_eur"] for d in days)
        net = sum(d["net_cost_eur"] for d in days)
        savings = sum(d["solar_savings_eur"] for d in days)
        revenue = sum(d["feed_in_revenue_eur"] for d in days)
        avg_price = sum(d["avg_price_eur_kwh"] for d in days) / len(days)

        cheapest = min(days, key=lambda d: d["net_cost_eur"])
        priciest = max(days, key=lambda d: d["net_cost_eur"])

        return CostBreakdown(
            gross_cost_eur=round(gross, 2),
            net_cost_eur=round(net, 2),
            solar_savings_eur=round(savings, 2),
            feed_in_revenue_eur=round(revenue, 2),
            avg_price_eur_kwh=round(avg_price, 4),
            cheapest_day=cheapest["date"],
            most_expensive_day=priciest["date"],
        )

    @staticmethod
    def _build_comparison(current: list[dict], previous: list[dict]) -> PeriodComparison:
        def _sum(days, key):
            return sum(d[key] for d in days) if days else 0

        c_cons = _sum(current, "consumption_kwh")
        p_cons = _sum(previous, "consumption_kwh")
        c_cost = _sum(current, "net_cost_eur")
        p_cost = _sum(previous, "net_cost_eur")
        c_prod = _sum(current, "production_kwh")
        p_prod = _sum(previous, "production_kwh")

        cons_change = ((c_cons - p_cons) / p_cons * 100) if p_cons > 0 else 0.0
        cost_change = ((c_cost - p_cost) / p_cost * 100) if p_cost > 0 else 0.0
        prod_change = ((c_prod - p_prod) / p_prod * 100) if p_prod > 0 else 0.0

        # Trend: lower consumption + lower cost = improving
        if cons_change < -3 and cost_change < -3:
            trend = "improving"
        elif cons_change > 3 and cost_change > 3:
            trend = "worsening"
        else:
            trend = "stable"

        # German summary
        if trend == "improving":
            summary = (
                f"Verbrauch um {abs(cons_change):.1f}% gesunken, "
                f"Kosten um {abs(cost_change):.1f}% reduziert. Weiter so!"
            )
        elif trend == "worsening":
            summary = (
                f"Verbrauch um {cons_change:.1f}% gestiegen, "
                f"Kosten um {cost_change:.1f}% hoeher. Optimierung empfohlen."
            )
        else:
            summary = "Verbrauch und Kosten auf stabilem Niveau."

        return PeriodComparison(
            consumption_change_pct=round(cons_change, 1),
            cost_change_pct=round(cost_change, 1),
            production_change_pct=round(prod_change, 1),
            trend=trend,
            summary_de=summary,
        )

    @staticmethod
    def _build_recommendations(
        days: list[dict],
        consumption: ConsumptionBreakdown,
        costs: CostBreakdown,
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []

        if not days:
            return recs

        # Low self-consumption
        if consumption.self_consumption_ratio_pct < 50 and consumption.total_production_kwh > 0:
            potential = consumption.fed_in_kwh * (costs.avg_price_eur_kwh - 0.082)
            recs.append(Recommendation(
                category="solar",
                title_de="Eigenverbrauch erhoehen",
                description_de=(
                    f"Nur {consumption.self_consumption_ratio_pct:.0f}% des Solarstroms "
                    "werden selbst verbraucht. Geraete in Sonnenstunden betreiben."
                ),
                potential_savings_eur=round(max(0, potential), 2),
                priority=1,
            ))

        # High grid dependency
        if consumption.autarky_ratio_pct < 50 and consumption.total_production_kwh > 0:
            recs.append(Recommendation(
                category="solar",
                title_de="Autarkiegrad verbessern",
                description_de=(
                    f"Nur {consumption.autarky_ratio_pct:.0f}% Autarkie. "
                    "Batteriespeicher oder Lastverschiebung koennte helfen."
                ),
                potential_savings_eur=round(consumption.net_grid_kwh * 0.05, 2),
                priority=2,
            ))

        # Expensive days pattern
        avg_daily = costs.net_cost_eur / max(len(days), 1)
        expensive_days = [d for d in days if d["net_cost_eur"] > avg_daily * 1.5]
        if expensive_days:
            recs.append(Recommendation(
                category="consumption",
                title_de="Verbrauchsspitzen reduzieren",
                description_de=(
                    f"{len(expensive_days)} Tage mit ueberdurchschnittlichen Kosten. "
                    "Grosse Verbraucher in guenstige Stunden verschieben."
                ),
                potential_savings_eur=round(
                    sum(d["net_cost_eur"] - avg_daily for d in expensive_days) * 0.3, 2
                ),
                priority=2,
            ))

        # Price optimization
        prices = [d["avg_price_eur_kwh"] for d in days]
        if prices and max(prices) - min(prices) > 0.05:
            recs.append(Recommendation(
                category="tariff",
                title_de="Dynamischen Tarif nutzen",
                description_de=(
                    f"Preisschwankung von {min(prices):.2f} bis {max(prices):.2f} EUR/kWh. "
                    "Verbrauch in guenstige Stunden verlagern."
                ),
                potential_savings_eur=round(consumption.net_grid_kwh * 0.03, 2),
                priority=3,
            ))

        # Schedule big consumers
        device_days = [d for d in days if d.get("devices")]
        if not device_days and len(days) > 1:
            recs.append(Recommendation(
                category="scheduling",
                title_de="Geraete-Tracking aktivieren",
                description_de=(
                    "Keine Geraetedaten vorhanden. Fingerprinting aktivieren "
                    "fuer detaillierte Geraeteanalyse."
                ),
                potential_savings_eur=0.0,
                priority=3,
            ))

        recs.sort(key=lambda r: r.priority)
        return recs

    @staticmethod
    def _build_highlights(
        consumption: ConsumptionBreakdown,
        costs: CostBreakdown,
        comparison: PeriodComparison,
        report_type: str,
    ) -> list[str]:
        highlights = []

        period_label = {"daily": "heute", "weekly": "diese Woche", "monthly": "diesen Monat"}
        period = period_label.get(report_type, "")

        highlights.append(
            f"Verbrauch {period}: {consumption.total_consumption_kwh:.1f} kWh"
        )

        if consumption.total_production_kwh > 0:
            highlights.append(
                f"PV-Erzeugung: {consumption.total_production_kwh:.1f} kWh "
                f"({consumption.autarky_ratio_pct:.0f}% Autarkie)"
            )

        highlights.append(
            f"Kosten: {costs.net_cost_eur:.2f} EUR "
            f"(gespart: {costs.solar_savings_eur:.2f} EUR durch Solar)"
        )

        if comparison.trend == "improving":
            highlights.append(
                f"Trend: Kosten um {abs(comparison.cost_change_pct):.1f}% gesunken"
            )
        elif comparison.trend == "worsening":
            highlights.append(
                f"Achtung: Kosten um {comparison.cost_change_pct:.1f}% gestiegen"
            )

        return highlights

    @staticmethod
    def _build_device_insights(days: list[dict]) -> list[dict]:
        """Aggregate device-level data across the period."""
        device_totals: dict[str, dict] = {}

        for d in days:
            for dev in d.get("devices", []):
                name = dev.get("device_name", "unknown")
                if name not in device_totals:
                    device_totals[name] = {"device_name": name, "total_kwh": 0, "total_runs": 0}
                device_totals[name]["total_kwh"] += dev.get("kwh", 0)
                device_totals[name]["total_runs"] += dev.get("runs", 0)

        insights = list(device_totals.values())
        for i in insights:
            i["total_kwh"] = round(i["total_kwh"], 2)

        insights.sort(key=lambda x: x["total_kwh"], reverse=True)
        return insights
