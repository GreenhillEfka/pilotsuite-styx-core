"""Tests for Reporting Engine — Slice 34."""
import pytest
from copilot_core.reporting.engine import (
    ReportingEngine,
    ReportFormat,
    ReportStatus,
    ReportSchedule,
    ReportDefinition,
    Report,
    create_reporting_engine,
)


class TestReportingEngine:
    """Test reporting engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_reporting_engine()
        assert engine is not None
    
    def test_create_report_json(self):
        """Test creating JSON report definition."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Daily Summary",
            description="Daily summary report",
            data_source="events",
            format="json",
            schedule="daily",
        )
        
        assert report_id is not None
        assert report_id.startswith("rpt_")
        assert report_id in engine._definitions
        
        definition = engine.get_report_definition(report_id)
        assert definition["format"] == "json"
        assert definition["schedule"] == "daily"
    
    def test_create_report_csv(self):
        """Test creating CSV report definition."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Weekly Export",
            description="Weekly CSV export",
            data_source="events",
            format="csv",
            schedule="weekly",
        )
        
        definition = engine.get_report_definition(report_id)
        assert definition["format"] == "csv"
    
    def test_create_report_html(self):
        """Test creating HTML report definition."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="HTML Dashboard",
            description="HTML dashboard report",
            data_source="metrics",
            format="html",
        )
        
        definition = engine.get_report_definition(report_id)
        assert definition["format"] == "html"
    
    def test_create_report_markdown(self):
        """Test creating Markdown report definition."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Markdown Report",
            description="Markdown format report",
            data_source="events",
            format="markdown",
        )
        
        definition = engine.get_report_definition(report_id)
        assert definition["format"] == "markdown"
    
    def test_create_report_with_filters(self):
        """Test creating report with filters."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Filtered Report",
            description="Report with filters",
            data_source="events",
            filters={"type": "motion", "zone": "entrance"},
        )
        
        definition = engine.get_report_definition(report_id)
        assert definition["filters"]["type"] == "motion"
    
    def test_create_report_with_aggregations(self):
        """Test creating report with aggregations."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Aggregated Report",
            description="Report with aggregations",
            data_source="events",
            aggregations=[
                {"type": "sum", "field": "duration", "group_by": "zone"},
            ],
        )
        
        definition = engine.get_report_definition(report_id)
        assert len(definition["aggregations"]) == 1
    
    def test_create_report_with_recipients(self):
        """Test creating report with recipients."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Distributed Report",
            description="Report with recipients",
            data_source="events",
            recipients=["user@example.com", "admin@example.com"],
        )
        
        definition = engine.get_report_definition(report_id)
        assert len(definition["recipients"]) == 2
    
    def test_register_data_source(self):
        """Test registering data source."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1, "value": 100}]
        
        engine.register_data_source("mock_events", mock_fetcher)
        
        assert "mock_events" in engine._data_sources
    
    def test_generate_report_json(self):
        """Test generating JSON report."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [
                {"id": 1, "name": "Event 1", "value": 100},
                {"id": 2, "name": "Event 2", "value": 200},
            ]
        
        engine.register_data_source("test_events", mock_fetcher)
        
        report_id = engine.create_report(
            name="Test Report",
            description="Test",
            data_source="test_events",
            format="json",
        )
        
        generated_id = engine.generate_report(report_id)
        
        assert generated_id is not None
        
        report = engine.get_report(generated_id)
        assert report["status"] == "completed"
        assert report["format"] == "json"
    
    def test_generate_report_csv(self):
        """Test generating CSV report."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [
                {"id": 1, "name": "Event 1", "value": 100},
                {"id": 2, "name": "Event 2", "value": 200},
            ]
        
        engine.register_data_source("test_events", mock_fetcher)
        
        report_id = engine.create_report(
            name="Test CSV Report",
            description="Test",
            data_source="test_events",
            format="csv",
            columns=["id", "name", "value"],
        )
        
        generated_id = engine.generate_report(report_id)
        
        report = engine.get_report(generated_id)
        assert report["status"] == "completed"
        
        content = engine.get_report_content(generated_id)
        assert "id,name,value" in content
    
    def test_generate_report_html(self):
        """Test generating HTML report."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [
                {"id": 1, "name": "Event 1"},
                {"id": 2, "name": "Event 2"},
            ]
        
        engine.register_data_source("test_events", mock_fetcher)
        
        report_id = engine.create_report(
            name="Test HTML Report",
            description="Test",
            data_source="test_events",
            format="html",
        )
        
        generated_id = engine.generate_report(report_id)
        
        content = engine.get_report_content(generated_id)
        assert "<table" in content
        assert "<th>" in content
    
    def test_generate_report_markdown(self):
        """Test generating Markdown report."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [
                {"id": 1, "name": "Event 1"},
                {"id": 2, "name": "Event 2"},
            ]
        
        engine.register_data_source("test_events", mock_fetcher)
        
        report_id = engine.create_report(
            name="Test MD Report",
            description="Test",
            data_source="test_events",
            format="markdown",
        )
        
        generated_id = engine.generate_report(report_id)
        
        content = engine.get_report_content(generated_id)
        assert "|" in content
        assert "---" in content
    
    def test_generate_report_unknown_source(self):
        """Test generating report with unknown data source."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Test Report",
            description="Test",
            data_source="unknown_source",
        )
        
        result = engine.generate_report(report_id)
        
        assert result is None
    
    def test_aggregation_sum(self):
        """Test sum aggregation."""
        engine = ReportingEngine()
        
        data = [
            {"zone": "A", "value": 10},
            {"zone": "A", "value": 20},
            {"zone": "B", "value": 30},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "sum", "field": "value", "group_by": "zone"},
        ])
        
        assert len(result) == 2
        
        zone_a = next(r for r in result if r["zone"] == "A")
        assert zone_a["value"] == 30
    
    def test_aggregation_count(self):
        """Test count aggregation."""
        engine = ReportingEngine()
        
        data = [
            {"zone": "A", "event": "motion"},
            {"zone": "A", "event": "door"},
            {"zone": "B", "event": "motion"},
            {"zone": "B", "event": "motion"},
            {"zone": "B", "event": "door"},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "count", "group_by": "zone"},
        ])
        
        zone_a = next(r for r in result if r["zone"] == "A")
        zone_b = next(r for r in result if r["zone"] == "B")
        
        assert zone_a["count"] == 2
        assert zone_b["count"] == 3
    
    def test_aggregation_average(self):
        """Test average aggregation."""
        engine = ReportingEngine()
        
        data = [
            {"zone": "A", "value": 10},
            {"zone": "A", "value": 20},
            {"zone": "B", "value": 30},
            {"zone": "B", "value": 40},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "average", "field": "value", "group_by": "zone"},
        ])
        
        zone_a = next(r for r in result if r["zone"] == "A")
        zone_b = next(r for r in result if r["zone"] == "B")
        
        assert zone_a["value"] == 15.0
        assert zone_b["value"] == 35.0
    
    def test_aggregation_filter(self):
        """Test filter aggregation."""
        engine = ReportingEngine()
        
        data = [
            {"type": "motion", "zone": "A"},
            {"type": "door", "zone": "A"},
            {"type": "motion", "zone": "B"},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "filter", "field": "type", "value": "motion"},
        ])
        
        assert len(result) == 2
        assert all(r["type"] == "motion" for r in result)
    
    def test_aggregation_sort(self):
        """Test sort aggregation."""
        engine = ReportingEngine()
        
        data = [
            {"name": "C", "value": 30},
            {"name": "A", "value": 10},
            {"name": "B", "value": 20},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "sort", "field": "name"},
        ])
        
        assert result[0]["name"] == "A"
        assert result[1]["name"] == "B"
        assert result[2]["name"] == "C"
    
    def test_aggregation_sort_descending(self):
        """Test sort descending aggregation."""
        engine = ReportingEngine()
        
        data = [
            {"name": "C", "value": 30},
            {"name": "A", "value": 10},
            {"name": "B", "value": 20},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "sort", "field": "name", "descending": True},
        ])
        
        assert result[0]["name"] == "C"
        assert result[1]["name"] == "B"
        assert result[2]["name"] == "A"
    
    def test_aggregation_limit(self):
        """Test limit aggregation."""
        engine = ReportingEngine()
        
        data = [{"id": i} for i in range(100)]
        
        result = engine._apply_aggregations(data, [
            {"type": "limit", "limit": 10},
        ])
        
        assert len(result) == 10
    
    def test_aggregation_chain(self):
        """Test chained aggregations."""
        engine = ReportingEngine()
        
        data = [
            {"zone": "A", "type": "motion", "value": 10},
            {"zone": "A", "type": "motion", "value": 20},
            {"zone": "A", "type": "door", "value": 5},
            {"zone": "B", "type": "motion", "value": 30},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "filter", "field": "type", "value": "motion"},
            {"type": "sum", "field": "value", "group_by": "zone"},
        ])
        
        assert len(result) == 2
    
    def test_get_report_definition(self):
        """Test getting report definition."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Test Report",
            description="Test description",
            data_source="events",
        )
        
        definition = engine.get_report_definition(report_id)
        
        assert definition is not None
        assert definition["name"] == "Test Report"
        assert definition["description"] == "Test description"
    
    def test_get_unknown_report_definition(self):
        """Test getting unknown report definition."""
        engine = ReportingEngine()
        
        definition = engine.get_report_definition("unknown")
        
        assert definition is None
    
    def test_get_all_report_definitions(self):
        """Test getting all report definitions."""
        engine = ReportingEngine()
        
        for i in range(3):
            engine.create_report(f"Report {i}", "Test", "events")
        
        definitions = engine.get_all_report_definitions()
        
        assert len(definitions) == 3
    
    def test_delete_report_definition(self):
        """Test deleting report definition."""
        engine = ReportingEngine()
        
        report_id = engine.create_report("Test Report", "Test", "events")
        
        result = engine.delete_report_definition(report_id)
        
        assert result is True
        assert engine.get_report_definition(report_id) is None
    
    def test_delete_unknown_report_definition(self):
        """Test deleting unknown report definition."""
        engine = ReportingEngine()
        
        result = engine.delete_report_definition("unknown")
        
        assert result is False
    
    def test_get_report(self):
        """Test getting generated report."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test")
        generated_id = engine.generate_report(report_id)
        
        report = engine.get_report(generated_id)
        
        assert report is not None
        assert report["definition_id"] == report_id
    
    def test_get_unknown_report(self):
        """Test getting unknown report."""
        engine = ReportingEngine()
        
        report = engine.get_report("unknown")
        
        assert report is None
    
    def test_get_report_content(self):
        """Test getting report content."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1, "value": 100}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test", format="json")
        generated_id = engine.generate_report(report_id)
        
        content = engine.get_report_content(generated_id)
        
        assert content is not None
        assert "id" in content
    
    def test_get_all_reports(self):
        """Test getting all reports."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test")
        
        for i in range(5):
            engine.generate_report(report_id)
        
        reports = engine.get_all_reports()
        
        assert len(reports) == 5
    
    def test_get_all_reports_filtered_by_definition(self):
        """Test getting reports filtered by definition."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report1 = engine.create_report("Report 1", "Test", "test")
        report2 = engine.create_report("Report 2", "Test", "test")
        
        engine.generate_report(report1)
        engine.generate_report(report2)
        engine.generate_report(report1)
        
        reports1 = engine.get_all_reports(definition_id=report1)
        
        assert len(reports1) == 2
    
    def test_get_all_reports_filtered_by_status(self):
        """Test getting reports filtered by status."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test")
        
        for i in range(3):
            engine.generate_report(report_id)
        
        completed = engine.get_all_reports(status="completed")
        failed = engine.get_all_reports(status="failed")
        
        assert len(completed) == 3
        assert len(failed) == 0
    
    def test_get_all_reports_limit(self):
        """Test getting reports with limit."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test")
        
        for i in range(10):
            engine.generate_report(report_id)
        
        reports = engine.get_all_reports(limit=5)
        
        assert len(reports) == 5
    
    def test_get_report_archive(self):
        """Test getting report archive."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test")
        
        for i in range(10):
            engine.generate_report(report_id)
        
        archive = engine.get_report_archive(limit=5)
        
        assert len(archive) == 5
    
    def test_get_reporting_statistics(self):
        """Test getting reporting statistics."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        engine.create_report("Report 1", "Test", "test", format="json")
        engine.create_report("Report 2", "Test", "test", format="csv")
        
        stats = engine.get_reporting_statistics()
        
        assert stats["total_definitions"] == 2
        assert stats["registered_data_sources"] >= 1
    
    def test_schedule_report_hourly(self):
        """Test hourly schedule calculation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Hourly Report",
            description="Test",
            data_source="events",
            schedule="hourly",
        )
        
        definition = engine.get_report_definition(report_id)
        
        assert definition["next_scheduled"] is not None
    
    def test_schedule_report_daily(self):
        """Test daily schedule calculation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Daily Report",
            description="Test",
            data_source="events",
            schedule="daily",
        )
        
        definition = engine.get_report_definition(report_id)
        
        assert definition["next_scheduled"] is not None
    
    def test_schedule_report_weekly(self):
        """Test weekly schedule calculation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Weekly Report",
            description="Test",
            data_source="events",
            schedule="weekly",
        )
        
        definition = engine.get_report_definition(report_id)
        
        assert definition["next_scheduled"] is not None
    
    def test_schedule_report_monthly(self):
        """Test monthly schedule calculation."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="Monthly Report",
            description="Test",
            data_source="events",
            schedule="monthly",
        )
        
        definition = engine.get_report_definition(report_id)
        
        assert definition["next_scheduled"] is not None
    
    def test_schedule_report_once(self):
        """Test once schedule (no next scheduled)."""
        engine = ReportingEngine()
        
        report_id = engine.create_report(
            name="One-Time Report",
            description="Test",
            data_source="events",
            schedule="once",
        )
        
        definition = engine.get_report_definition(report_id)
        
        assert definition["next_scheduled"] is None
    
    def test_process_scheduled_reports(self):
        """Test processing scheduled reports."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        # Create report with past schedule (will be due)
        report_id = engine.create_report(
            name="Due Report",
            description="Test",
            data_source="test",
            schedule="hourly",
        )
        
        # Manually set next_scheduled to past
        engine._definitions[report_id].next_scheduled = "2020-01-01T00:00:00Z"
        
        processed = engine.process_scheduled_reports()
        
        assert processed >= 1
    
    def test_export_json_empty_data(self):
        """Test JSON export with empty data."""
        engine = ReportingEngine()
        
        content, mime_type = engine._export_json([], [])
        
        assert content == "[]"
        assert mime_type == "application/json"
    
    def test_export_csv_empty_data(self):
        """Test CSV export with empty data."""
        engine = ReportingEngine()
        
        content, mime_type = engine._export_csv([], [])
        
        assert content == ""
        assert mime_type == "text/csv"
    
    def test_export_html_empty_data(self):
        """Test HTML export with empty data."""
        engine = ReportingEngine()
        
        content, mime_type = engine._export_html([], [])
        
        assert "<table" in content
        assert mime_type == "text/html"
    
    def test_export_markdown_empty_data(self):
        """Test Markdown export with empty data."""
        engine = ReportingEngine()
        
        content, mime_type = engine._export_markdown([], [])
        
        assert content == ""
        assert mime_type == "text/markdown"
    
    def test_report_definition_to_dict(self):
        """Test report definition serialization."""
        definition = ReportDefinition(
            report_id="rpt_test",
            name="Test Report",
            description="Test",
            data_source="events",
            format=ReportFormat.JSON,
            schedule=ReportSchedule.DAILY,
        )
        
        d = definition.to_dict()
        
        assert d["report_id"] == "rpt_test"
        assert d["format"] == "json"
        assert d["schedule"] == "daily"
    
    def test_report_to_dict(self):
        """Test report serialization."""
        report = Report(
            report_id="report_test",
            definition_id="rpt_test",
            status=ReportStatus.COMPLETED,
            format=ReportFormat.JSON,
            data="{}",
            generated_at="2026-03-31T12:00:00Z",
            file_size_bytes=2,
        )
        
        d = report.to_dict()
        
        assert d["report_id"] == "report_test"
        assert d["status"] == "completed"
        assert d["file_size_bytes"] == 2
    
    def test_report_format_enum_values(self):
        """Test report format enum values."""
        assert ReportFormat.JSON.value == "json"
        assert ReportFormat.CSV.value == "csv"
        assert ReportFormat.PDF.value == "pdf"
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.MARKDOWN.value == "markdown"
    
    def test_report_status_enum_values(self):
        """Test report status enum values."""
        assert ReportStatus.PENDING.value == "pending"
        assert ReportStatus.GENERATING.value == "generating"
        assert ReportStatus.COMPLETED.value == "completed"
        assert ReportStatus.FAILED.value == "failed"
    
    def test_report_schedule_enum_values(self):
        """Test report schedule enum values."""
        assert ReportSchedule.ONCE.value == "once"
        assert ReportSchedule.HOURLY.value == "hourly"
        assert ReportSchedule.DAILY.value == "daily"
        assert ReportSchedule.WEEKLY.value == "weekly"
        assert ReportSchedule.MONTHLY.value == "monthly"
        assert ReportSchedule.YEARLY.value == "yearly"
    
    def test_reports_sorted_by_generated_at(self):
        """Test that reports are sorted by generated_at."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test")
        
        for i in range(5):
            engine.generate_report(report_id)
        
        reports = engine.get_all_reports(limit=10)
        
        # Verify sorted (newest first)
        for i in range(len(reports) - 1):
            assert reports[i]["generated_at"] >= reports[i + 1]["generated_at"]
    
    def test_archive_trimmed_to_max(self):
        """Test that archive is trimmed to max size."""
        engine = ReportingEngine()
        engine._max_archive_size = 10
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test")
        
        for i in range(20):
            engine.generate_report(report_id)
        
        assert len(engine._report_archive) <= 10
    
    def test_register_custom_exporter(self):
        """Test registering custom exporter."""
        engine = ReportingEngine()
        
        def custom_exporter(data, columns):
            return "custom", "text/custom"
        
        engine.register_exporter(ReportFormat.PDF, custom_exporter)
        
        assert ReportFormat.PDF in engine._exporters
    
    def test_aggregation_filter_gt(self):
        """Test filter aggregation with greater than."""
        engine = ReportingEngine()
        
        data = [
            {"value": 10},
            {"value": 20},
            {"value": 30},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "filter", "field": "value", "value": 15, "operator": "gt"},
        ])
        
        assert len(result) == 2
        assert all(r["value"] > 15 for r in result)
    
    def test_aggregation_filter_lt(self):
        """Test filter aggregation with less than."""
        engine = ReportingEngine()
        
        data = [
            {"value": 10},
            {"value": 20},
            {"value": 30},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "filter", "field": "value", "value": 25, "operator": "lt"},
        ])
        
        assert len(result) == 2
        assert all(r["value"] < 25 for r in result)
    
    def test_aggregation_filter_contains(self):
        """Test filter aggregation with contains."""
        engine = ReportingEngine()
        
        data = [
            {"name": "Event A"},
            {"name": "Event B"},
            {"name": "Other"},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "filter", "field": "name", "value": "Event", "operator": "contains"},
        ])
        
        assert len(result) == 2
        assert all("Event" in r["name"] for r in result)
    
    def test_aggregation_filter_ne(self):
        """Test filter aggregation with not equal."""
        engine = ReportingEngine()
        
        data = [
            {"type": "motion"},
            {"type": "door"},
            {"type": "motion"},
        ]
        
        result = engine._apply_aggregations(data, [
            {"type": "filter", "field": "type", "value": "motion", "operator": "ne"},
        ])
        
        assert len(result) == 1
        assert result[0]["type"] == "door"
    
    def test_generate_report_updates_definition(self):
        """Test that generating report updates definition."""
        engine = ReportingEngine()
        
        def mock_fetcher(filters=None):
            return [{"id": 1}]
        
        engine.register_data_source("test", mock_fetcher)
        
        report_id = engine.create_report("Test", "Test", "test", schedule="hourly")
        
        definition_before = engine.get_report_definition(report_id)
        
        engine.generate_report(report_id)
        
        definition_after = engine.get_report_definition(report_id)
        
        assert definition_after["last_generated"] is not None
    
    def test_statistics_empty_engine(self):
        """Test statistics with empty engine."""
        engine = ReportingEngine()
        
        stats = engine.get_reporting_statistics()
        
        assert stats["total_definitions"] == 0
        assert stats["total_reports"] == 0
    
    def test_csv_export_columns_order(self):
        """Test CSV export respects column order."""
        engine = ReportingEngine()
        
        data = [
            {"c": 3, "a": 1, "b": 2},
            {"c": 6, "a": 4, "b": 5},
        ]
        
        content, _ = engine._export_csv(data, ["a", "b", "c"])
        
        lines = content.strip().split("\n")
        header = lines[0]
        
        assert header == "a,b,c"
    
    def test_html_export_columns_order(self):
        """Test HTML export respects column order."""
        engine = ReportingEngine()
        
        data = [
            {"c": 3, "a": 1, "b": 2},
        ]
        
        content, _ = engine._export_html(data, ["a", "b", "c"])
        
        assert "<th>a</th>" in content
        assert "<th>b</th>" in content
        assert "<th>c</th>" in content
    
    def test_markdown_export_columns_order(self):
        """Test Markdown export respects column order."""
        engine = ReportingEngine()
        
        data = [
            {"c": 3, "a": 1, "b": 2},
        ]
        
        content, _ = engine._export_markdown(data, ["a", "b", "c"])
        
        lines = content.strip().split("\n")
        header = lines[0]
        
        assert header == "| a | b | c |"
