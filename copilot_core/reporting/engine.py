"""PilotSuite Reporting Engine — Automated Reports."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# REPORT TYPES
# =============================================================================

class ReportType(Enum):
    """Types of reports."""
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"
    ENERGY_REPORT = "energy_report"
    AUTOMATION_REPORT = "automation_report"
    SECURITY_REPORT = "security_report"


@dataclass
class Report:
    """Report data structure."""
    report_type: ReportType
    title: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    sections: List[Dict[str, Any]]
    summary: str
    data: Dict[str, Any]


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class ReportGenerator:
    """
    Report Generator
    
    Features:
    - Daily/Weekly/Monthly summaries
    - Energy reports
    - Automation performance
    - Security audits
    - Email/Notification delivery
    
    Usage:
    ```python
    from copilot_core.reporting import ReportGenerator
    
    generator = ReportGenerator()
    report = await generator.generate_daily_summary()
    ```
    """

    def __init__(self, hass=None):
        self.hass = hass

    async def generate_daily_summary(self, date: Optional[datetime] = None) -> Report:
        """Generate daily summary report."""
        date = date or datetime.now()
        period_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=1)
        
        sections = []
        
        # Presence summary
        presence_data = await self._get_presence_summary(period_start, period_end)
        sections.append({
            "title": "Presence",
            "data": presence_data,
        })
        
        # Energy summary
        energy_data = await self._get_energy_summary(period_start, period_end)
        sections.append({
            "title": "Energy",
            "data": energy_data,
        })
        
        # Automation summary
        automation_data = await self._get_automation_summary(period_start, period_end)
        sections.append({
            "title": "Automations",
            "data": automation_data,
        })
        
        return Report(
            report_type=ReportType.DAILY_SUMMARY,
            title=f"Daily Summary - {date.strftime('%Y-%m-%d')}",
            generated_at=datetime.now(),
            period_start=period_start,
            period_end=period_end,
            sections=sections,
            summary=self._generate_summary(sections),
            data={
                "presence": presence_data,
                "energy": energy_data,
                "automations": automation_data,
            }
        )

    async def generate_weekly_summary(self, weeks_ago: int = 0) -> Report:
        """Generate weekly summary report."""
        now = datetime.now() - timedelta(weeks=weeks_ago)
        period_start = now - timedelta(days=now.weekday())
        period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(weeks=1)
        
        sections = []
        
        # Aggregate daily data
        daily_reports = []
        for day in range(7):
            day_date = period_start + timedelta(days=day)
            if day_date < now:
                daily_reports.append(await self.generate_daily_summary(day_date))
        
        sections.append({
            "title": "Weekly Overview",
            "data": {
                "days": len(daily_reports),
                "reports": daily_reports,
            },
        })
        
        return Report(
            report_type=ReportType.WEEKLY_SUMMARY,
            title=f"Weekly Summary - Week {period_start.isocalendar()[1]}",
            generated_at=datetime.now(),
            period_start=period_start,
            period_end=period_end,
            sections=sections,
            summary=self._generate_summary(sections),
            data={"daily_reports": daily_reports}
        )

    async def generate_energy_report(self, period_days: int = 30) -> Report:
        """Generate energy report."""
        now = datetime.now()
        period_start = now - timedelta(days=period_days)
        
        sections = []
        
        # Consumption
        consumption_data = await self._get_energy_consumption(period_start, now)
        sections.append({
            "title": "Consumption",
            "data": consumption_data,
        })
        
        # Solar production
        solar_data = await self._get_solar_production(period_start, now)
        sections.append({
            "title": "Solar Production",
            "data": solar_data,
        })
        
        # Savings
        savings_data = await self._get_energy_savings(period_start, now)
        sections.append({
            "title": "Savings",
            "data": savings_data,
        })
        
        return Report(
            report_type=ReportType.ENERGY_REPORT,
            title=f"Energy Report - Last {period_days} days",
            generated_at=datetime.now(),
            period_start=period_start,
            period_end=now,
            sections=sections,
            summary=f"Total consumption: {consumption_data.get('total_kwh', 0):.1f} kWh, "
                   f"Savings: {savings_data.get('total_ct', 0):.2f}€",
            data={
                "consumption": consumption_data,
                "solar": solar_data,
                "savings": savings_data,
            }
        )

    async def generate_automation_report(self, period_days: int = 7) -> Report:
        """Generate automation performance report."""
        now = datetime.now()
        period_start = now - timedelta(days=period_days)
        
        sections = []
        
        # Execution stats
        execution_data = await self._get_automation_executions(period_start, now)
        sections.append({
            "title": "Execution Statistics",
            "data": execution_data,
        })
        
        # Top automations
        top_automations = await self._get_top_automations(period_start, now)
        sections.append({
            "title": "Top Automations",
            "data": top_automations,
        })
        
        # Failures
        failures = await self._get_automation_failures(period_start, now)
        sections.append({
            "title": "Failures",
            "data": failures,
        })
        
        return Report(
            report_type=ReportType.AUTOMATION_REPORT,
            title=f"Automation Report - Last {period_days} days",
            generated_at=datetime.now(),
            period_start=period_start,
            period_end=now,
            sections=sections,
            summary=f"Total executions: {execution_data.get('total', 0)}, "
                   f"Success rate: {execution_data.get('success_rate', 0):.1f}%",
            data={
                "executions": execution_data,
                "top_automations": top_automations,
                "failures": failures,
            }
        )

    async def _get_presence_summary(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Get presence summary for period."""
        # Would query database
        return {
            "hours_home": 0,
            "hours_away": 0,
            "confidence_avg": 0,
        }

    async def _get_energy_summary(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Get energy summary for period."""
        return {
            "consumption_kwh": 0,
            "solar_kwh": 0,
            "savings_ct": 0,
        }

    async def _get_automation_summary(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Get automation summary for period."""
        return {
            "executions": 0,
            "success_rate": 0,
            "avg_execution_time_ms": 0,
        }

    async def _get_energy_consumption(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Get energy consumption data."""
        return {"total_kwh": 0, "daily": []}

    async def _get_solar_production(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Get solar production data."""
        return {"total_kwh": 0, "daily": []}

    async def _get_energy_savings(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Get energy savings data."""
        return {"total_ct": 0, "daily": []}

    async def _get_automation_executions(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Get automation execution stats."""
        return {"total": 0, "success_rate": 100}

    async def _get_top_automations(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Get top executed automations."""
        return []

    async def _get_automation_failures(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Get automation failures."""
        return []

    def _generate_summary(self, sections: List[Dict[str, Any]]) -> str:
        """Generate human-readable summary."""
        # Would generate natural language summary
        return "Report generated successfully"


# =============================================================================
# REPORT DELIVERY
# =============================================================================

class ReportDelivery:
    """Deliver reports via various channels."""

    def __init__(self, notification_manager=None):
        self.notification_manager = notification_manager

    async def deliver_email(self, report: Report, recipients: List[str]):
        """Deliver report via email."""
        # Would send email
        logger.info(f"Email report to {recipients}: {report.title}")

    async def deliver_notification(self, report: Report, chat_ids: List[str]):
        """Deliver report via notification."""
        if self.notification_manager:
            from copilot_core.integrations.notifications import Notification, NotificationPriority
            
            notification = Notification(
                title=report.title,
                message=report.summary,
                priority=NotificationPriority.NORMAL,
            )
            await self.notification_manager.send(notification)

    async def deliver_to_file(self, report: Report, filepath: str):
        """Save report to file."""
        import json
        
        data = {
            "title": report.title,
            "generated_at": report.generated_at.isoformat(),
            "period": {
                "start": report.period_start.isoformat(),
                "end": report.period_end.isoformat(),
            },
            "summary": report.summary,
            "sections": report.sections,
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Report saved to {filepath}")


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_reporting(hass, config: Dict[str, Any]):
    """Set up reporting in Home Assistant."""
    generator = ReportGenerator(hass)
    delivery = ReportDelivery()
    
    # Store in hass.data
    hass.data["pilotsuite_report_generator"] = generator
    hass.data["pilotsuite_report_delivery"] = delivery
    
    logger.info("Reporting set up successfully")
    
    return generator, delivery
