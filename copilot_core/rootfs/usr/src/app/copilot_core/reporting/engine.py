"""Reporting Engine — Slice 34.

Automated reporting for PilotSuite Core.

Features:
- Scheduled report generation
- Multiple output formats (JSON, CSV, PDF)
- Custom report templates
- Data aggregation and filtering
- Report distribution
- Historical report archive
"""
from __future__ import annotations

import logging
import json
import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Report output format."""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"


class ReportStatus(Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportSchedule(Enum):
    """Report schedule frequency."""
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class ReportDefinition:
    """Report definition."""
    report_id: str
    name: str
    description: str
    data_source: str  # Data source identifier
    filters: Dict[str, Any] = field(default_factory=dict)
    aggregations: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    format: ReportFormat = ReportFormat.JSON
    schedule: ReportSchedule = ReportSchedule.ONCE
    recipients: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_generated: Optional[str] = None
    next_scheduled: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "name": self.name,
            "description": self.description,
            "data_source": self.data_source,
            "filters": self.filters,
            "aggregations": self.aggregations,
            "columns": self.columns,
            "format": self.format.value,
            "schedule": self.schedule.value,
            "recipients": self.recipients,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_generated": self.last_generated,
            "next_scheduled": self.next_scheduled,
        }


@dataclass
class Report:
    """Generated report instance."""
    report_id: str
    definition_id: str
    status: ReportStatus
    format: ReportFormat
    data: Any
    generated_at: str
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "definition_id": self.definition_id,
            "status": self.status.value,
            "format": self.format.value,
            "generated_at": self.generated_at,
            "error_message": self.error_message,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
        }


class ReportingEngine:
    """Automated reporting engine."""
    
    def __init__(self):
        self._definitions: Dict[str, ReportDefinition] = {}
        self._reports: Dict[str, Report] = {}
        self._data_sources: Dict[str, Callable] = {}
        self._exporters: Dict[ReportFormat, Callable] = {}
        self._report_archive: List[Report] = []
        self._max_archive_size = 100
        
        # Register built-in exporters
        self._register_builtin_exporters()
    
    def _register_builtin_exporters(self) -> None:
        """Register built-in format exporters."""
        self._exporters[ReportFormat.JSON] = self._export_json
        self._exporters[ReportFormat.CSV] = self._export_csv
        self._exporters[ReportFormat.HTML] = self._export_html
        self._exporters[ReportFormat.MARKDOWN] = self._export_markdown
    
    def _export_json(self, data: Any, columns: List[str]) -> tuple:
        """Export data as JSON."""
        content = json.dumps(data, indent=2, default=str)
        return content, "application/json"
    
    def _export_csv(self, data: Any, columns: List[str]) -> tuple:
        """Export data as CSV."""
        output = io.StringIO()
        
        if not data:
            return "", "text/csv"
        
        # Determine columns from data if not provided
        if not columns and isinstance(data, list) and len(data) > 0:
            columns = list(data[0].keys())
        
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        
        for row in data:
            writer.writerow(row)
        
        return output.getvalue(), "text/csv"
    
    def _export_html(self, data: Any, columns: List[str]) -> tuple:
        """Export data as HTML table."""
        if not data:
            return "<table></table>", "text/html"
        
        if not columns and isinstance(data, list) and len(data) > 0:
            columns = list(data[0].keys())
        
        html = ["<table border='1'>", "<thead><tr>"]
        
        for col in columns:
            html.append(f"<th>{col}</th>")
        
        html.append("</tr></thead><tbody>")
        
        for row in data:
            html.append("<tr>")
            for col in columns:
                value = row.get(col, "")
                html.append(f"<td>{value}</td>")
            html.append("</tr>")
        
        html.append("</tbody></table>")
        
        return "\n".join(html), "text/html"
    
    def _export_markdown(self, data: Any, columns: List[str]) -> tuple:
        """Export data as Markdown table."""
        if not data:
            return "", "text/markdown"
        
        if not columns and isinstance(data, list) and len(data) > 0:
            columns = list(data[0].keys())
        
        lines = []
        
        # Header
        header = "| " + " | ".join(columns) + " |"
        lines.append(header)
        
        # Separator
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        lines.append(separator)
        
        # Rows
        for row in data:
            values = [str(row.get(col, "")) for col in columns]
            line = "| " + " | ".join(values) + " |"
            lines.append(line)
        
        return "\n".join(lines), "text/markdown"
    
    def register_data_source(self, source_name: str,
                            fetcher: Callable) -> None:
        """Register a data source fetcher."""
        self._data_sources[source_name] = fetcher
        logger.info("Data source registered: %s", source_name)
    
    def register_exporter(self, format: ReportFormat,
                         exporter: Callable) -> None:
        """Register a custom format exporter."""
        self._exporters[format] = exporter
        logger.info("Exporter registered: %s", format.value)
    
    def create_report(self, name: str, description: str,
                     data_source: str,
                     filters: Optional[Dict[str, Any]] = None,
                     aggregations: Optional[List[Dict[str, Any]]] = None,
                     columns: Optional[List[str]] = None,
                     format: str = "json",
                     schedule: str = "once",
                     recipients: Optional[List[str]] = None) -> str:
        """Create a report definition."""
        report_id = f"rpt_{uuid.uuid4().hex[:8]}"
        
        definition = ReportDefinition(
            report_id=report_id,
            name=name,
            description=description,
            data_source=data_source,
            filters=filters or {},
            aggregations=aggregations or [],
            columns=columns or [],
            format=ReportFormat(format),
            schedule=ReportSchedule(schedule),
            recipients=recipients or [],
        )
        
        # Calculate next scheduled run
        definition.next_scheduled = self._calculate_next_schedule(definition)
        
        self._definitions[report_id] = definition
        
        logger.info("Report created: %s (%s)", name, report_id)
        
        return report_id
    
    def _calculate_next_schedule(self, definition: ReportDefinition) -> Optional[str]:
        """Calculate next scheduled run time."""
        now = datetime.now(timezone.utc)
        
        if definition.schedule == ReportSchedule.ONCE:
            return None
        
        elif definition.schedule == ReportSchedule.HOURLY:
            next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return next_run.isoformat()
        
        elif definition.schedule == ReportSchedule.DAILY:
            next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return next_run.isoformat()
        
        elif definition.schedule == ReportSchedule.WEEKLY:
            # Next Monday
            days_ahead = 7 - now.weekday()  # Monday is 0
            if days_ahead == 7:
                days_ahead = 0
            next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
            return next_run.isoformat()
        
        elif definition.schedule == ReportSchedule.MONTHLY:
            # First of next month
            if now.month == 12:
                next_run = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                next_run = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return next_run.isoformat()
        
        elif definition.schedule == ReportSchedule.YEARLY:
            next_run = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return next_run.isoformat()
        
        return None
    
    def generate_report(self, report_id: str) -> Optional[str]:
        """Generate a report."""
        if report_id not in self._definitions:
            logger.error("Report definition not found: %s", report_id)
            return None
        
        definition = self._definitions[report_id]
        
        # Get data source
        if definition.data_source not in self._data_sources:
            logger.error("Unknown data source: %s", definition.data_source)
            return None
        
        fetcher = self._data_sources[definition.data_source]
        
        # Fetch data
        try:
            raw_data = fetcher(filters=definition.filters)
        except Exception as exc:
            logger.exception("Data fetch failed: %s", exc)
            return None
        
        # Apply aggregations
        aggregated_data = self._apply_aggregations(raw_data, definition.aggregations)
        
        # Export to format
        if definition.format not in self._exporters:
            logger.error("Unknown export format: %s", definition.format.value)
            return None
        
        exporter = self._exporters[definition.format]
        content, mime_type = exporter(aggregated_data, definition.columns)
        
        # Create report instance
        report_id_out = f"report_{uuid.uuid4().hex[:8]}"
        
        report = Report(
            report_id=report_id_out,
            definition_id=report_id,
            status=ReportStatus.COMPLETED,
            format=definition.format,
            data=content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            file_size_bytes=len(content.encode('utf-8')),
        )
        
        self._reports[report_id_out] = report
        
        # Update definition
        definition.last_generated = report.generated_at
        definition.next_scheduled = self._calculate_next_schedule(definition)
        
        # Archive report
        self._report_archive.append(report)
        if len(self._report_archive) > self._max_archive_size:
            self._report_archive = self._report_archive[-self._max_archive_size:]
        
        logger.info("Report generated: %s (%d bytes)", report_id_out, report.file_size_bytes)
        
        return report_id_out
    
    def _apply_aggregations(self, data: List[Dict[str, Any]],
                           aggregations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply aggregations to data."""
        if not aggregations:
            return data
        
        result = data
        
        for agg in aggregations:
            agg_type = agg.get("type")
            field = agg.get("field")
            
            if agg_type == "sum":
                # Group by and sum
                group_by = agg.get("group_by")
                if group_by:
                    grouped = {}
                    for row in result:
                        key = row.get(group_by)
                        if key not in grouped:
                            grouped[key] = {group_by: key, field: 0}
                        grouped[key][field] += row.get(field, 0)
                    result = list(grouped.values())
            
            elif agg_type == "count":
                group_by = agg.get("group_by")
                if group_by:
                    grouped = {}
                    for row in result:
                        key = row.get(group_by)
                        if key not in grouped:
                            grouped[key] = {group_by: key, "count": 0}
                        grouped[key]["count"] += 1
                    result = list(grouped.values())
            
            elif agg_type == "average":
                group_by = agg.get("group_by")
                if group_by:
                    grouped = {}
                    sums = {}
                    counts = {}
                    for row in result:
                        key = row.get(group_by)
                        if key not in grouped:
                            grouped[key] = {group_by: key, field: 0}
                            sums[key] = 0
                            counts[key] = 0
                        sums[key] += row.get(field, 0)
                        counts[key] += 1
                    for key in grouped:
                        grouped[key][field] = sums[key] / counts[key] if counts[key] > 0 else 0
                    result = list(grouped.values())
            
            elif agg_type == "filter":
                # Filter rows
                filter_field = agg.get("field")
                filter_value = agg.get("value")
                filter_op = agg.get("operator", "eq")
                
                filtered = []
                for row in result:
                    row_value = row.get(filter_field)
                    
                    if filter_op == "eq" and row_value == filter_value:
                        filtered.append(row)
                    elif filter_op == "ne" and row_value != filter_value:
                        filtered.append(row)
                    elif filter_op == "gt" and row_value > filter_value:
                        filtered.append(row)
                    elif filter_op == "lt" and row_value < filter_value:
                        filtered.append(row)
                    elif filter_op == "contains" and filter_value in str(row_value):
                        filtered.append(row)
                
                result = filtered
            
            elif agg_type == "sort":
                sort_field = agg.get("field")
                reverse = agg.get("descending", False)
                result = sorted(result, key=lambda x: x.get(sort_field, ""), reverse=reverse)
            
            elif agg_type == "limit":
                limit = agg.get("limit", 100)
                result = result[:limit]
        
        return result
    
    def get_report_definition(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report definition."""
        if report_id not in self._definitions:
            return None
        
        return self._definitions[report_id].to_dict()
    
    def get_all_report_definitions(self) -> List[Dict[str, Any]]:
        """Get all report definitions."""
        return [d.to_dict() for d in self._definitions.values()]
    
    def delete_report_definition(self, report_id: str) -> bool:
        """Delete a report definition."""
        if report_id not in self._definitions:
            return False
        
        del self._definitions[report_id]
        return True
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get generated report."""
        if report_id not in self._reports:
            return None
        
        return self._reports[report_id].to_dict()
    
    def get_report_content(self, report_id: str) -> Optional[str]:
        """Get report content."""
        if report_id not in self._reports:
            return None
        
        return self._reports[report_id].data
    
    def get_all_reports(self, definition_id: Optional[str] = None,
                       status: Optional[str] = None,
                       limit: int = 50) -> List[Dict[str, Any]]:
        """Get all generated reports."""
        reports = list(self._reports.values())
        
        if definition_id:
            reports = [r for r in reports if r.definition_id == definition_id]
        
        if status:
            reports = [r for r in reports if r.status.value == status]
        
        # Sort by generated_at (newest first)
        reports.sort(key=lambda r: r.generated_at, reverse=True)
        
        return [r.to_dict() for r in reports[:limit]]
    
    def get_report_archive(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get archived reports."""
        archive = self._report_archive[-limit:]
        archive.reverse()  # Newest first
        return [r.to_dict() for r in archive]
    
    def get_reporting_statistics(self) -> Dict[str, Any]:
        """Get reporting statistics."""
        total_definitions = len(self._definitions)
        total_reports = len(self._reports)
        
        by_format = {}
        for report in self._reports.values():
            fmt = report.format.value
            by_format[fmt] = by_format.get(fmt, 0) + 1
        
        by_status = {}
        for report in self._reports.values():
            status = report.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        total_size_bytes = sum(r.file_size_bytes for r in self._reports.values())
        
        return {
            "total_definitions": total_definitions,
            "total_reports": total_reports,
            "by_format": by_format,
            "by_status": by_status,
            "total_size_bytes": total_size_bytes,
            "archive_size": len(self._report_archive),
            "registered_data_sources": len(self._data_sources),
        }
    
    def schedule_report(self, report_id: str) -> bool:
        """Update next scheduled run for a report."""
        if report_id not in self._definitions:
            return False
        
        definition = self._definitions[report_id]
        definition.next_scheduled = self._calculate_next_schedule(definition)
        
        return True
    
    def process_scheduled_reports(self) -> int:
        """Process all due scheduled reports."""
        now = datetime.now(timezone.utc)
        processed = 0
        
        for definition in self._definitions.values():
            if definition.schedule == ReportSchedule.ONCE:
                continue
            
            if not definition.next_scheduled:
                continue
            
            next_run = datetime.fromisoformat(definition.next_scheduled)
            
            if next_run <= now:
                self.generate_report(definition.report_id)
                processed += 1
        
        return processed


def create_reporting_engine() -> ReportingEngine:
    """Factory function to create reporting engine."""
    return ReportingEngine()
