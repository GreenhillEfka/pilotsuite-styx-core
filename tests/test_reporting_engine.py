"""Tests for Reporting Engine — Slice 22."""
import pytest
from copilot_core.reporting.engine import (
    ReportingEngine,
    ReportType,
    ReportFormat,
    DeliveryChannel,
    create_reporting_engine,
)
from datetime import datetime, timezone, timedelta


class TestReportingEngine:
    """Test reporting engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_reporting_engine()
        assert engine is not None
    
    def test_create_report_definition(self):
        """Test report definition creation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Daily Summary",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=["user@example.com"],
            delivery_channels=[DeliveryChannel.EMAIL, DeliveryChannel.STORAGE],
            include_sections=["energy", "security"],
        )
        
        assert report_id is not None
        assert report_id in engine._definitions
        assert engine._definitions[report_id].name == "Daily Summary"
    
    def test_generate_daily_summary_report(self):
        """Test daily summary report generation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Daily Summary",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=["user@example.com"],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=["energy", "security"],
        )
        
        report = engine.generate_report(report_id)
        
        assert report is not None
        assert report.definition_id == report_id
        assert report.format == ReportFormat.JSON
    
    def test_generate_weekly_summary_report(self):
        """Test weekly summary report generation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Weekly Summary",
            report_type=ReportType.WEEKLY_SUMMARY,
            format=ReportFormat.HTML,
            schedule="weekly",
            recipients=["user@example.com"],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=["energy", "weather"],
        )
        
        report = engine.generate_report(report_id)
        
        assert report is not None
        assert "Weekly Summary" in report.content
    
    def test_generate_monthly_summary_report(self):
        """Test monthly summary report generation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Monthly Summary",
            report_type=ReportType.MONTHLY_SUMMARY,
            format=ReportFormat.MARKDOWN,
            schedule="monthly",
            recipients=["user@example.com"],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=["energy"],
        )
        
        report = engine.generate_report(report_id)
        
        assert report is not None
        assert "Monthly Summary" in report.content
    
    def test_generate_energy_report(self):
        """Test energy report generation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Energy Report",
            report_type=ReportType.ENERGY_REPORT,
            format=ReportFormat.JSON,
            schedule="weekly",
            recipients=[],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=["consumption"],
        )
        
        report = engine.generate_report(report_id)
        
        assert report is not None
        assert report.data["report_type"] == "energy_report"
    
    def test_generate_security_report(self):
        """Test security report generation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Security Report",
            report_type=ReportType.SECURITY_REPORT,
            format=ReportFormat.HTML,
            schedule="daily",
            recipients=[],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=["alerts"],
        )
        
        report = engine.generate_report(report_id)
        
        assert report is not None
        assert report.data["report_type"] == "security_report"
    
    def test_get_report(self):
        """Test getting a generated report."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Test Report",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=[],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=[],
        )
        
        generated = engine.generate_report(report_id)
        
        # Get by report_id
        retrieved = engine.get_report(generated.report_id)
        
        assert retrieved is not None
        assert retrieved["report_id"] == generated.report_id
    
    def test_get_reports_by_definition(self):
        """Test getting reports by definition."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Test Report",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=[],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=[],
        )
        
        # Generate multiple reports
        for i in range(5):
            engine.generate_report(report_id)
        
        reports = engine.get_reports_by_definition(report_id, limit=10)
        
        assert len(reports) == 5
    
    def test_enable_disable_report(self):
        """Test enabling/disabling reports."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Test Report",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=[],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=[],
        )
        
        # Disable
        result = engine.disable_report(report_id)
        assert result is True
        assert engine._definitions[report_id].enabled is False
        
        # Try to generate (should return None)
        report = engine.generate_report(report_id)
        assert report is None
        
        # Enable
        result = engine.enable_report(report_id)
        assert result is True
        assert engine._definitions[report_id].enabled is True
    
    def test_get_all_definitions(self):
        """Test getting all definitions."""
        engine = ReportingEngine()
        
        engine.create_report_definition("Report 1", ReportType.DAILY_SUMMARY, ReportFormat.JSON, "daily", [], [DeliveryChannel.STORAGE], [])
        engine.create_report_definition("Report 2", ReportType.WEEKLY_SUMMARY, ReportFormat.HTML, "weekly", [], [DeliveryChannel.STORAGE], [])
        
        definitions = engine.get_all_definitions()
        
        assert len(definitions) == 2
    
    def test_report_format_json(self):
        """Test JSON format output."""
        engine = ReportingEngine()
        
        content = {"title": "Test", "sections": [{"name": "Section 1", "data": "Data 1"}]}
        
        formatted = engine._format_content(content, ReportFormat.JSON)
        
        assert "Test" in formatted
        assert "Section 1" in formatted
        assert formatted.startswith("{")
    
    def test_report_format_html(self):
        """Test HTML format output."""
        engine = ReportingEngine()
        
        content = {"title": "Test Report", "period": "2026-03-31", "sections": [{"name": "Section 1", "data": "Data 1"}]}
        
        formatted = engine._format_content(content, ReportFormat.HTML)
        
        assert "<h1>Test Report</h1>" in formatted
        assert "<li>" in formatted
    
    def test_report_format_markdown(self):
        """Test Markdown format output."""
        engine = ReportingEngine()
        
        content = {"title": "Test Report", "period": "2026-03-31", "sections": [{"name": "Section 1", "data": "Data 1"}]}
        
        formatted = engine._format_content(content, ReportFormat.MARKDOWN)
        
        assert "# Test Report" in formatted
        assert "**Section 1**" in formatted
    
    def test_report_format_csv(self):
        """Test CSV format output."""
        engine = ReportingEngine()
        
        content = {"title": "Test", "sections": [{"name": "Section 1", "data": "Data 1"}, {"name": "Section 2", "data": "Data 2"}]}
        
        formatted = engine._format_content(content, ReportFormat.CSV)
        
        assert "Section,Data" in formatted
        assert "Section 1,Data 1" in formatted
    
    def test_next_run_calculation_daily(self):
        """Test next run calculation for daily schedule."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Daily",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=[],
            delivery_channels=[],
            include_sections=[],
        )
        
        definition = engine._definitions[report_id]
        
        # Next run should be set
        assert definition.next_run is not None
    
    def test_archive_management(self):
        """Test report archive management."""
        engine = ReportingEngine()
        engine._max_archive_size = 5
        
        report_id = engine.create_report_definition(
            name="Test",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=[],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=[],
        )
        
        # Generate 7 reports (exceeds max archive size)
        for i in range(7):
            engine.generate_report(report_id)
        
        # Archive should be trimmed to max size
        assert len(engine._archive) == 5
    
    def test_get_reporting_summary(self):
        """Test reporting summary."""
        engine = ReportingEngine()
        
        # Create definitions
        engine.create_report_definition("Report 1", ReportType.DAILY_SUMMARY, ReportFormat.JSON, "daily", [], [DeliveryChannel.STORAGE], [])
        engine.create_report_definition("Report 2", ReportType.WEEKLY_SUMMARY, ReportFormat.HTML, "weekly", [], [DeliveryChannel.STORAGE], [])
        
        # Disable one
        engine.disable_report("report_2")
        
        # Generate some reports
        engine.generate_report("report_1")
        engine.generate_report("report_1")
        
        summary = engine.get_reporting_summary()
        
        assert summary["total_definitions"] == 2
        assert summary["enabled_reports"] == 1
        assert summary["total_generated"] == 2
    
    def test_disabled_report_not_generated(self):
        """Test that disabled reports are not generated."""
        engine = ReportingEngine()
        
        report_id = engine.create_report_definition(
            name="Test",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=[],
            delivery_channels=[DeliveryChannel.STORAGE],
            include_sections=[],
        )
        
        # Disable before generating
        engine.disable_report(report_id)
        
        report = engine.generate_report(report_id)
        
        assert report is None
    
    def test_unknown_definition_returns_none(self):
        """Test that unknown definition returns None."""
        engine = ReportingEngine()
        
        report = engine.generate_report("unknown_definition")
        
        assert report is None
    
    def test_get_unknown_report_returns_none(self):
        """Test that getting unknown report returns None."""
        engine = ReportingEngine()
        
        report = engine.get_report("unknown_report")
        
        assert report is None
    
    def test_report_definition_to_dict(self):
        """Test report definition serialization."""
        from copilot_core.reporting.engine import ReportDefinition
        
        definition = ReportDefinition(
            report_id="report_test",
            name="Test Report",
            report_type=ReportType.DAILY_SUMMARY,
            format=ReportFormat.JSON,
            schedule="daily",
            recipients=["user@example.com"],
            delivery_channels=[DeliveryChannel.EMAIL],
            include_sections=["energy"],
        )
        
        d = definition.to_dict()
        
        assert d["report_id"] == "report_test"
        assert d["name"] == "Test Report"
        assert d["report_type"] == "daily_summary"
        assert d["format"] == "json"
        assert d["recipients"] == ["user@example.com"]
    
    def test_generated_report_to_dict(self):
        """Test generated report serialization."""
        from copilot_core.reporting.engine import GeneratedReport, ReportFormat
        
        report = GeneratedReport(
            report_id="gen_test",
            definition_id="report_test",
            generated_at="2026-03-31T08:00:00Z",
            period_start="2026-03-30T00:00:00Z",
            period_end="2026-03-31T00:00:00Z",
            format=ReportFormat.JSON,
            content='{"title": "Test"}',
            data={"test": "data"},
            file_path="/data/reports/gen_test.json",
        )
        
        d = report.to_dict()
        
        assert d["report_id"] == "gen_test"
        assert d["definition_id"] == "report_test"
        assert d["format"] == "json"
        assert d["file_path"] == "/data/reports/gen_test.json"
        assert "content_preview" in d
