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
from typing import Optional


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

    # ── Internal builders ───────────────────────────────────────────────

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
