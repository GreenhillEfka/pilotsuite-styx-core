from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"))

from main import create_app


def test_analytics_contract_exposes_minimal_read_only_overview():
    client = create_app({"TESTING": True}).test_client()

    response = client.get("/api/v1/analytics")
    assert response.status_code == 200

    assert response.get_json() == {
        "ok": True,
        "source": "static_analytics_overview",
        "generated_at": "2026-04-08T04:32:00+00:00",
        "time_range_days": 30,
        "refresh_interval_seconds": 60,
        "overall_health_score": 0.79,
        "overall_status": "warning",
        "zones_active": 4,
        "zones_total": 10,
        "module_cards": [
            {
                "module_id": "zone_truth",
                "module_name": "Zone Truth",
                "health_score": 0.87,
                "status": "healthy",
                "total_events": 1243,
                "key_metrics": {
                    "sync_success_rate": 0.93,
                    "conflict_rate": 0.07,
                },
                "trend_7d": 0.02,
                "trend_30d": 0.05,
                "last_updated": "2026-04-08T04:20:00+00:00",
            },
            {
                "module_id": "presence",
                "module_name": "Presence",
                "health_score": 0.81,
                "status": "healthy",
                "total_events": 318,
                "key_metrics": {
                    "home_rate": 0.67,
                    "hold_rate": 0.0,
                },
                "trend_7d": 0.01,
                "trend_30d": 0.03,
                "last_updated": "2026-04-08T04:18:00+00:00",
            },
            {
                "module_id": "dashboard_layout",
                "module_name": "Dashboard Layout",
                "health_score": 0.7,
                "status": "warning",
                "total_events": 96,
                "key_metrics": {
                    "undo_success_rate": 0.92,
                    "reset_events": 4,
                },
                "trend_7d": -0.01,
                "trend_30d": 0.04,
                "last_updated": "2026-04-08T04:12:00+00:00",
            },
        ],
        "kpis": [
            {
                "kpi_id": "household_presence_coverage",
                "kpi_name": "Household Presence Coverage",
                "current_value": 0.67,
                "target_value": 0.95,
                "unit": "ratio",
                "delta_24h": 0.0,
                "delta_7d": 0.04,
                "status": "at_risk",
            },
            {
                "kpi_id": "zone_catalog_completeness",
                "kpi_name": "Habitus Zone Catalog Completeness",
                "current_value": 10,
                "target_value": 10,
                "unit": "zones",
                "delta_24h": 0.0,
                "delta_7d": 0.0,
                "status": "on_track",
            },
            {
                "kpi_id": "widget_layout_reliability",
                "kpi_name": "Widget Layout Reliability",
                "current_value": 0.92,
                "target_value": 0.98,
                "unit": "ratio",
                "delta_24h": 0.01,
                "delta_7d": 0.03,
                "status": "at_risk",
            },
        ],
        "attention_required": [
            {
                "severity": "medium",
                "module": "presence",
                "issue": "Presence coverage still partial",
                "metric": "home_rate",
                "current_value": 0.67,
                "target_value": 0.95,
            },
            {
                "severity": "medium",
                "module": "dashboard_layout",
                "issue": "Widget layout reliability below target",
                "metric": "undo_success_rate",
                "current_value": 0.92,
                "target_value": 0.98,
            },
        ],
    }
