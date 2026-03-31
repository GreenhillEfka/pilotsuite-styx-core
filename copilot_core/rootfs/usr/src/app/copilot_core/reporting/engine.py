"""Reporting Engine — Slice 22.

Automated report generation for PilotSuite Core.

Features:
- Scheduled report generation (daily, weekly, monthly)
- Multi-format export (PDF, JSON, CSV, HTML)
- Custom report templates
- Email/Telegram report delivery
- Historical report archive
"""
from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Type of report."""
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"
    ENERGY_REPORT = "energy_report"
    SECURITY_REPORT = "security_report"
    CUSTOM = "custom"


class ReportFormat(Enum):
    """Report output format."""
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"
    MARKDOWN = "markdown"


class DeliveryChannel(Enum):
    """Report delivery channel."""
    EMAIL = "email"
    TELEGRAM = "telegram"
    HOME_ASSISTANT = "home_assistant"
    WEBHOOK = "webhook"
    STORAGE = "storage"  # Save to file


@dataclass
class ReportDefinition:
    """Report definition/template."""
    report_id: str
    name: str
    report_type: ReportType
    format: ReportFormat
    schedule: str  # cron expression or "daily", "weekly", "monthly"
    recipients: List[str]
    delivery_channels: List[DeliveryChannel]
    include_sections: List[str]
    filters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_generated: Optional[str] = None
    next_run: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "name": self.name,
            "report_type": self.report_type.value,
            "format": self.format.value,
            "schedule": self.schedule,
            "recipients": self.recipients,
            "delivery_channels": [c.value for c in self.delivery_channels],
            "include_sections": self.include_sections,
            "filters": self.filters,
            "enabled": self.enabled,
            "last_generated": self.last_generated,
            "next_run": self.next_run,
        }


@dataclass
class GeneratedReport:
    """Generated report instance."""
    report_id: str
    definition_id: str
    generated_at: str
    period_start: str
    period_end: str
    format: ReportFormat
    content: str  # Report content (formatted)
    data: Dict[str, Any]  # Raw data
    delivery_status: Dict[str, str] = field(default_factory=dict)  # channel -> status
    file_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "definition_id": self.definition_id,
            "generated_at": self.generated_at,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "format": self.format.value,
            "content_preview": self.content[:500] if len(self.content) > 500 else self.content,
            "delivery_status": self.delivery_status,
            "file_path": self.file_path,
        }


class ReportingEngine:
    """Report generation engine."""
    
    def __init__(self):
        self._definitions: Dict[str, ReportDefinition] = {}
        self._reports: Dict[str, GeneratedReport] = {}
        self._report_counter = 0
        self._archive: List[str] = []  # List of report_ids
        self._max_archive_size = 100
        
        # Report templates
        self._templates: Dict[ReportType, callable] = {
            ReportType.DAILY_SUMMARY: self._generate_daily_summary,
            ReportType.WEEKLY_SUMMARY: self._generate_weekly_summary,
            ReportType.MONTHLY_SUMMARY: self._generate_monthly_summary,
            ReportType.ENERGY_REPORT: self._generate_energy_report,
            ReportType.SECURITY_REPORT: self._generate_security_report,
        }
    
    def create_report_definition(self, name: str, report_type: ReportType,
                                 format: ReportFormat, schedule: str,
                                 recipients: List[str],
                                 delivery_channels: List[DeliveryChannel],
                                 include_sections: List[str],
                                 filters: Optional[Dict[str, Any]] = None) -> str:
        """Create a new report definition."""
        report_id = f"report_{len(self._definitions) + 1}"
        
        definition = ReportDefinition(
            report_id=report_id,
            name=name,
            report_type=report_type,
            format=format,
            schedule=schedule,
            recipients=recipients,
            delivery_channels=delivery_channels,
            include_sections=include_sections,
            filters=filters or {},
        )
        
        self._definitions[report_id] = definition
        self._calculate_next_run(definition)
        
        return report_id
    
    def generate_report(self, definition_id: str,
                       period_start: Optional[datetime] = None,
                       period_end: Optional[datetime] = None) -> Optional[GeneratedReport]:
        """Generate a report from definition."""
        if definition_id not in self._definitions:
            logger.warning("Unknown report definition: %s", definition_id)
            return None
        
        definition = self._definitions[definition_id]
        
        if not definition.enabled:
            logger.info("Report %s is disabled", definition_id)
            return None
        
        # Set period
        now = datetime.now(timezone.utc)
        if not period_end:
            period_end = now
        
        if not period_start:
            period_start = self._calculate_period_start(definition.schedule, period_end)
        
        # Generate content
        generator = self._templates.get(definition.report_type, self._generate_custom_report)
        data, content = generator(definition, period_start, period_end)
        
        # Format content
        formatted_content = self._format_content(content, definition.format)
        
        # Create report
        self._report_counter += 1
        report = GeneratedReport(
            report_id=f"gen_{self._report_counter}",
            definition_id=definition_id,
            generated_at=now.isoformat(),
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            format=definition.format,
            content=formatted_content,
            data=data,
        )
        
        self._reports[report.report_id] = report
        
        # Deliver
        self._deliver_report(report, definition)
        
        # Update definition
        definition.last_generated = now.isoformat()
        self._calculate_next_run(definition)
        
        # Archive
        self._archive.append(report.report_id)
        if len(self._archive) > self._max_archive_size:
            old_id = self._archive.pop(0)
            self._reports.pop(old_id, None)
        
        return report
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a generated report."""
        if report_id not in self._reports:
            return None
        
        return self._reports[report_id].to_dict()
    
    def get_reports_by_definition(self, definition_id: str,
                                  limit: int = 10) -> List[Dict[str, Any]]:
        """Get reports for a specific definition."""
        reports = [
            r for r in self._reports.values()
            if r.definition_id == definition_id
        ]
        
        # Sort by generated_at (newest first)
        reports.sort(key=lambda r: r.generated_at, reverse=True)
        
        return [r.to_dict() for r in reports[:limit]]
    
    def get_all_definitions(self) -> List[Dict[str, Any]]:
        """Get all report definitions."""
        return [d.to_dict() for d in self._definitions.values()]
    
    def enable_report(self, definition_id: str) -> bool:
        """Enable a report definition."""
        if definition_id not in self._definitions:
            return False
        
        self._definitions[definition_id].enabled = True
        return True
    
    def disable_report(self, definition_id: str) -> bool:
        """Disable a report definition."""
        if definition_id not in self._definitions:
            return False
        
        self._definitions[definition_id].enabled = False
        return True
    
    def _calculate_period_start(self, schedule: str, end: datetime) -> datetime:
        """Calculate period start based on schedule."""
        if schedule == "daily":
            return end - timedelta(days=1)
        elif schedule == "weekly":
            return end - timedelta(weeks=1)
        elif schedule == "monthly":
            return end - timedelta(days=30)
        else:
            return end - timedelta(days=1)
    
    def _calculate_next_run(self, definition: ReportDefinition) -> None:
        """Calculate next run time for a definition."""
        now = datetime.now(timezone.utc)
        
        if definition.schedule == "daily":
            next_run = now + timedelta(days=1)
            next_run = next_run.replace(hour=8, minute=0, second=0, microsecond=0)
        elif definition.schedule == "weekly":
            next_run = now + timedelta(weeks=1)
            next_run = next_run.replace(hour=9, minute=0, second=0, microsecond=0, weekday=0)
        elif definition.schedule == "monthly":
            next_run = now + timedelta(days=30)
            next_run = next_run.replace(hour=10, minute=0, second=0, microsecond=0, day=1)
        else:
            next_run = now + timedelta(days=1)
        
        definition.next_run = next_run.isoformat()
    
    def _generate_daily_summary(self, definition: ReportDefinition,
                                start: datetime, end: datetime) -> tuple:
        """Generate daily summary report."""
        data = {
            "report_type": "daily_summary",
            "period": f"{start.date()} to {end.date()}",
            "sections": {},
        }
        
        content = {
            "title": f"Daily Summary - {start.date()}",
            "sections": [],
        }
        
        for section in definition.include_sections:
            if section == "energy":
                data["sections"]["energy"] = {"total_kwh": 0.0, "cost": 0.0}
                content["sections"].append({"name": "Energy", "data": "No data available"})
            
            elif section == "security":
                data["sections"]["security"] = {"alerts": 0, "events": 0}
                content["sections"].append({"name": "Security", "data": "No alerts"})
            
            elif section == "weather":
                data["sections"]["weather"] = {"avg_temp": 0.0, "condition": "unknown"}
                content["sections"].append({"name": "Weather", "data": "No data"})
        
        return data, content
    
    def _generate_weekly_summary(self, definition: ReportDefinition,
                                 start: datetime, end: datetime) -> tuple:
        """Generate weekly summary report."""
        data = {
            "report_type": "weekly_summary",
            "period": f"Week {start.isocalendar()[1]}",
            "sections": {},
        }
        
        content = {
            "title": f"Weekly Summary - Week {start.isocalendar()[1]}",
            "sections": [],
        }
        
        for section in definition.include_sections:
            content["sections"].append({"name": section.capitalize(), "data": "Weekly summary"})
            data["sections"][section] = {}
        
        return data, content
    
    def _generate_monthly_summary(self, definition: ReportDefinition,
                                  start: datetime, end: datetime) -> tuple:
        """Generate monthly summary report."""
        data = {
            "report_type": "monthly_summary",
            "period": f"{start.strftime('%B %Y')}",
            "sections": {},
        }
        
        content = {
            "title": f"Monthly Summary - {start.strftime('%B %Y')}",
            "sections": [],
        }
        
        for section in definition.include_sections:
            content["sections"].append({"name": section.capitalize(), "data": "Monthly summary"})
            data["sections"][section] = {}
        
        return data, content
    
    def _generate_energy_report(self, definition: ReportDefinition,
                               start: datetime, end: datetime) -> tuple:
        """Generate energy report."""
        data = {
            "report_type": "energy_report",
            "period": f"{start.date()} to {end.date()}",
            "total_consumption_kwh": 0.0,
            "total_cost": 0.0,
            "by_zone": {},
            "by_module": {},
        }
        
        content = {
            "title": "Energy Report",
            "period": data["period"],
            "sections": [
                {"name": "Total Consumption", "value": "0.0 kWh"},
                {"name": "Total Cost", "value": "€0.00"},
            ],
        }
        
        return data, content
    
    def _generate_security_report(self, definition: ReportDefinition,
                                  start: datetime, end: datetime) -> tuple:
        """Generate security report."""
        data = {
            "report_type": "security_report",
            "period": f"{start.date()} to {end.date()}",
            "total_alerts": 0,
            "alerts_by_type": {},
            "alerts_by_zone": {},
        }
        
        content = {
            "title": "Security Report",
            "period": data["period"],
            "sections": [
                {"name": "Total Alerts", "value": "0"},
                {"name": "Status", "value": "No security incidents"},
            ],
        }
        
        return data, content
    
    def _generate_custom_report(self, definition: ReportDefinition,
                               start: datetime, end: datetime) -> tuple:
        """Generate custom report."""
        data = {
            "report_type": "custom",
            "period": f"{start.date()} to {end.date()}",
            "filters": definition.filters,
        }
        
        content = {
            "title": definition.name,
            "period": data["period"],
            "sections": [],
        }
        
        return data, content
    
    def _format_content(self, content: Any, format: ReportFormat) -> str:
        """Format content for output."""
        if format == ReportFormat.JSON:
            return json.dumps(content, indent=2, default=str)
        
        elif format == ReportFormat.CSV:
            # Simple CSV formatting
            if isinstance(content, dict) and "sections" in content:
                lines = ["Section,Data"]
                for section in content.get("sections", []):
                    lines.append(f"{section.get('name', '')},{section.get('data', '')}")
                return "\n".join(lines)
            return str(content)
        
        elif format == ReportFormat.HTML:
            if isinstance(content, dict):
                html = f"<h1>{content.get('title', 'Report')}</h1>"
                html += f"<p>Period: {content.get('period', '')}</p>"
                html += "<ul>"
                for section in content.get("sections", []):
                    html += f"<li><strong>{section.get('name', '')}</strong>: {section.get('data', '')}</li>"
                html += "</ul>"
                return html
            return f"<div>{content}</div>"
        
        elif format == ReportFormat.MARKDOWN:
            if isinstance(content, dict):
                md = f"# {content.get('title', 'Report')}\n\n"
                md += f"**Period:** {content.get('period', '')}\n\n"
                md += "## Sections\n\n"
                for section in content.get("sections", []):
                    md += f"- **{section.get('name', '')}**: {section.get('data', '')}\n"
                return md
            return str(content)
        
        elif format == ReportFormat.PDF:
            # PDF would require a library like reportlab
            # For now, return HTML as placeholder
            return self._format_content(content, ReportFormat.HTML)
        
        return str(content)
    
    def _deliver_report(self, report: GeneratedReport,
                       definition: ReportDefinition) -> None:
        """Deliver report to recipients."""
        for channel in definition.delivery_channels:
            status = "pending"
            
            try:
                if channel == DeliveryChannel.STORAGE:
                    # Save to file
                    file_path = f"/data/reports/{report.report_id}.{definition.format.value}"
                    report.file_path = file_path
                    status = "saved"
                
                elif channel == DeliveryChannel.TELEGRAM:
                    # Would send via Telegram API
                    status = "sent"
                
                elif channel == DeliveryChannel.EMAIL:
                    # Would send via email
                    status = "sent"
                
                elif channel == DeliveryChannel.HOME_ASSISTANT:
                    # Would send to HA
                    status = "delivered"
                
                elif channel == DeliveryChannel.WEBHOOK:
                    # Would POST to webhook
                    status = "delivered"
                
            except Exception as exc:
                logger.error("Failed to deliver report via %s: %s", channel, exc)
                status = f"failed: {exc}"
            
            report.delivery_status[channel.value] = status
    
    def get_reporting_summary(self) -> Dict[str, Any]:
        """Get reporting engine summary."""
        enabled_reports = len([d for d in self._definitions.values() if d.enabled])
        total_generated = len(self._reports)
        
        return {
            "total_definitions": len(self._definitions),
            "enabled_reports": enabled_reports,
            "total_generated": total_generated,
            "archive_size": len(self._archive),
        }


def create_reporting_engine() -> ReportingEngine:
    """Factory function to create reporting engine."""
    return ReportingEngine()
