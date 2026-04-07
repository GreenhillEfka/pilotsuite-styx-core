"""
Reporting Engine for PilotSuite Core.

Daily, weekly, and monthly report generation.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import json

_LOGGER = logging.getLogger(__name__)

REPORTS_PATH = Path("/config/copilot_core/data/reports")
REPORTS_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class Report:
    """Generated report."""
    id: str
    type: str  # daily, weekly, monthly
    period_start: datetime
    period_end: datetime
    generated_at: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class DailyReportGenerator:
    """Daily report generator."""

    def __init__(self, db_manager) -> None:
        """Initialize daily report generator."""
        self._db = db_manager

    def generate(self, date: Optional[datetime] = None) -> Report:
        """Generate daily report."""
        date = date or datetime.now()
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        # Gather metrics
        data = self._gather_daily_metrics(start, end)
        summary = self._generate_summary(data)

        report = Report(
            id=f"daily_{date.strftime('%Y%m%d')}",
            type="daily",
            period_start=start,
            period_end=end,
            data=data,
            summary=summary,
        )

        self._save_report(report)
        _LOGGER.info("Daily report generated: %s", report.id)
        return report

    def _gather_daily_metrics(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Gather metrics for the day."""
        return {
            "total_events": self._count_events(start, end),
            "presence_events": self._count_presence_events(start, end),
            "energy_consumption": self._get_energy_consumption(start, end),
            "patterns_learned": self._count_patterns_learned(start, end),
            "notifications_sent": self._count_notifications(start, end),
            "zones_active": self._get_active_zones(start, end),
        }

    def _count_events(self, start: datetime, end: datetime) -> int:
        """Count events in period."""
        rows = self._db.execute(
            "SELECT COUNT(*) as count FROM events WHERE timestamp BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat())
        )
        return rows[0]["count"] if rows else 0

    def _count_presence_events(self, start: datetime, end: datetime) -> int:
        """Count presence events."""
        rows = self._db.execute(
            "SELECT COUNT(*) as count FROM events WHERE event_type LIKE '%presence%' AND timestamp BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat())
        )
        return rows[0]["count"] if rows else 0

    def _get_energy_consumption(self, start: datetime, end: datetime) -> float:
        """Get energy consumption in kWh."""
        # Placeholder - would query energy module
        return 0.0

    def _count_patterns_learned(self, start: datetime, end: datetime) -> int:
        """Count new patterns learned."""
        rows = self._db.execute(
            "SELECT COUNT(*) as count FROM patterns WHERE created_at BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat())
        )
        return rows[0]["count"] if rows else 0

    def _count_notifications(self, start: datetime, end: datetime) -> int:
        """Count notifications sent."""
        rows = self._db.execute(
            "SELECT COUNT(*) as count FROM events WHERE event_type LIKE '%notification%' AND timestamp BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat())
        )
        return rows[0]["count"] if rows else 0

    def _get_active_zones(self, start: datetime, end: datetime) -> List[str]:
        """Get list of active zones."""
        rows = self._db.execute(
            "SELECT DISTINCT z.name FROM zones z JOIN entities e ON z.id = e.zone_id WHERE e.last_changed BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat())
        )
        return [row["name"] for row in rows]

    def _generate_summary(self, data: Dict[str, Any]) -> str:
        """Generate human-readable summary."""
        return (
            f"Daily Summary: {data['total_events']} events, "
            f"{data['presence_events']} presence events, "
            f"{data['patterns_learned']} new patterns learned, "
            f"{len(data['zones_active'])} zones active"
        )

    def _save_report(self, report: Report) -> None:
        """Save report to file."""
        path = REPORTS_PATH / f"{report.id}.json"
        with open(path, "w") as f:
            json.dump({
                "id": report.id,
                "type": report.type,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "generated_at": report.generated_at.isoformat(),
                "data": report.data,
                "summary": report.summary,
            }, f, indent=2)


class WeeklyReportGenerator:
    """Weekly report generator."""

    def __init__(self, db_manager) -> None:
        """Initialize weekly report generator."""
        self._db = db_manager
        self._daily = DailyReportGenerator(db_manager)

    def generate(self, date: Optional[datetime] = None) -> Report:
        """Generate weekly report."""
        date = date or datetime.now()
        start = date - timedelta(days=date.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(weeks=1)

        # Aggregate daily reports
        daily_reports = self._load_daily_reports(start, end)
        data = self._aggregate_weekly_data(daily_reports)
        summary = self._generate_summary(data)

        report = Report(
            id=f"weekly_{start.strftime('%Y%m%d')}",
            type="weekly",
            period_start=start,
            period_end=end,
            data=data,
            summary=summary,
        )

        self._save_report(report)
        _LOGGER.info("Weekly report generated: %s", report.id)
        return report

    def _load_daily_reports(self, start: datetime, end: datetime) -> List[Report]:
        """Load daily reports for the week."""
        reports = []
        current = start
        while current < end:
            path = REPORTS_PATH / f"daily_{current.strftime('%Y%m%d')}.json"
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                    reports.append(Report(
                        id=data["id"],
                        type=data["type"],
                        period_start=datetime.fromisoformat(data["period_start"]),
                        period_end=datetime.fromisoformat(data["period_end"]),
                        data=data["data"],
                        summary=data.get("summary", ""),
                    ))
            current += timedelta(days=1)
        return reports

    def _aggregate_weekly_data(self, daily_reports: List[Report]) -> Dict[str, Any]:
        """Aggregate daily data into weekly summary."""
        return {
            "total_events": sum(r.data.get("total_events", 0) for r in daily_reports),
            "total_presence_events": sum(r.data.get("presence_events", 0) for r in daily_reports),
            "total_patterns_learned": sum(r.data.get("patterns_learned", 0) for r in daily_reports),
            "total_notifications": sum(r.data.get("notifications_sent", 0) for r in daily_reports),
            "daily_breakdown": [
                {"date": r.period_start.strftime("%Y-%m-%d"), "events": r.data.get("total_events", 0)}
                for r in daily_reports
            ],
        }

    def _generate_summary(self, data: Dict[str, Any]) -> str:
        """Generate weekly summary."""
        avg_daily = data["total_events"] / 7 if data["total_events"] else 0
        return (
            f"Weekly Summary: {data['total_events']} total events "
            f"(avg {avg_daily:.1f}/day), "
            f"{data['total_patterns_learned']} patterns learned"
        )

    def _save_report(self, report: Report) -> None:
        """Save report to file."""
        path = REPORTS_PATH / f"{report.id}.json"
        with open(path, "w") as f:
            json.dump({
                "id": report.id,
                "type": report.type,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "generated_at": report.generated_at.isoformat(),
                "data": report.data,
                "summary": report.summary,
            }, f, indent=2)


class ReportDistributor:
    """Report distribution via email, Telegram, etc."""

    def __init__(self, notification_manager=None) -> None:
        """Initialize distributor."""
        self._notification_manager = notification_manager

    async def send_report(self, report: Report, channels: List[str] = None) -> bool:
        """Send report via configured channels."""
        channels = channels or ["telegram"]
        message = self._format_report_message(report)

        for channel in channels:
            try:
                if self._notification_manager:
                    await self._notification_manager.send(
                        channel=channel,
                        title=f"PilotSuite {report.type.capitalize()} Report",
                        message=message,
                    )
                _LOGGER.info("Report sent via %s", channel)
            except Exception as e:
                _LOGGER.error("Failed to send via %s: %s", channel, e)
                return False
        return True

    def _format_report_message(self, report: Report) -> str:
        """Format report as message."""
        lines = [
            f"📊 *PilotSuite {report.type.capitalize()} Report*",
            f"",
            f"📅 Period: {report.period_start.strftime('%Y-%m-%d')} - {report.period_end.strftime('%Y-%m-%d')}",
            f"",
            f"*Summary:*",
            report.summary,
            f"",
            f"*Key Metrics:*",
        ]

        for key, value in report.data.items():
            if isinstance(value, (int, float)) and key != "daily_breakdown":
                lines.append(f"  • {key.replace('_', ' ').title()}: {value}")

        return "\n".join(lines)


# Global instances
_daily_generator: Optional[DailyReportGenerator] = None
_weekly_generator: Optional[WeeklyReportGenerator] = None


def get_daily_report_generator(db_manager) -> DailyReportGenerator:
    """Get daily report generator."""
    global _daily_generator
    if _daily_generator is None:
        _daily_generator = DailyReportGenerator(db_manager)
    return _daily_generator


def get_weekly_report_generator(db_manager) -> WeeklyReportGenerator:
    """Get weekly report generator."""
    global _weekly_generator
    if _weekly_generator is None:
        _weekly_generator = WeeklyReportGenerator(db_manager)
    return _weekly_generator


__all__ = [
    "DailyReportGenerator",
    "WeeklyReportGenerator",
    "ReportDistributor",
    "Report",
    "get_daily_report_generator",
    "get_weekly_report_generator",
]
