from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"))

from main import create_app


@pytest.fixture()
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_notifications_contract_exposes_minimal_read_only_feed(client):
    response = client.get("/api/v1/notifications")
    assert response.status_code == 200

    assert response.get_json() == {
        "ok": True,
        "count": 3,
        "notifications": [
            {
                "id": "notif_presence_hold_office",
                "title": "Presence Hold aktiv",
                "message": "Office bleibt bis 08:30 im Hold, obwohl aktuell niemand zuhause gemeldet ist.",
                "priority": "high",
                "type": "alert",
                "timestamp": "2026-04-08T04:40:00+00:00",
                "action_data": {
                    "zone": "office",
                    "hold_until": "2026-04-08T08:30:00+00:00",
                },
                "action_url": "/presence",
                "target_devices": [],
                "target_users": [],
                "read": False,
                "dismissed": False,
                "sent": True,
                "source": "presence",
                "tags": ["presence", "hold"],
            },
            {
                "id": "notif_widget_layout_reset",
                "title": "Dashboard-Layout angepasst",
                "message": "Widget-Positionen wurden nach dem letzten Reset neu sortiert.",
                "priority": "normal",
                "type": "info",
                "timestamp": "2026-04-08T04:28:00+00:00",
                "action_data": {
                    "layout": "family_dashboard",
                },
                "action_url": "/dashboard",
                "target_devices": [],
                "target_users": [],
                "read": True,
                "dismissed": False,
                "sent": True,
                "source": "dashboard_layout",
                "tags": ["dashboard", "layout"],
            },
            {
                "id": "notif_zone_catalog_review",
                "title": "Zone-Katalog prüfen",
                "message": "Habitus-Zonen sind vollständig, aber Outdoor-Tags sollten erneut validiert werden.",
                "priority": "low",
                "type": "suggestion",
                "timestamp": "2026-04-08T04:12:00+00:00",
                "action_data": {
                    "zone_type": "outside",
                },
                "action_url": "/zones",
                "target_devices": [],
                "target_users": [],
                "read": False,
                "dismissed": False,
                "sent": True,
                "source": "zone_truth",
                "tags": ["zones", "review"],
            },
        ],
        "unread_count": 2,
        "total_count": 3,
    }


def test_notifications_contract_supports_limit_and_exact_filters(client):
    filtered = client.get("/api/v1/notifications?unread_only=true&type=alert&source=presence&limit=1")
    assert filtered.status_code == 200
    assert filtered.get_json()["count"] == 1
    assert filtered.get_json()["notifications"][0]["id"] == "notif_presence_hold_office"

    invalid_limit = client.get("/api/v1/notifications?limit=0")
    assert invalid_limit.status_code == 400
    assert invalid_limit.get_json()["error"] == "invalid_limit"


def test_notifications_digest_contract_exposes_minimal_summary_follow_up_slice(client):
    response = client.get("/api/v1/notifications/digest")
    assert response.status_code == 200

    assert response.get_json() == {
        "ok": True,
        "digest": {
            "period": "last_24h",
            "total": 3,
            "unread": 2,
            "read": 1,
            "dismissed": 0,
            "sent": 3,
            "by_type": {
                "alert": 1,
                "info": 1,
                "suggestion": 1,
            },
            "by_source": {
                "presence": 1,
                "dashboard_layout": 1,
                "zone_truth": 1,
            },
            "by_priority": {
                "high": 1,
                "normal": 1,
                "low": 1,
            },
            "latest_timestamp": "2026-04-08T04:40:00+00:00",
        },
    }


def test_notifications_stats_contract_exposes_minimal_read_only_stats_follow_up_slice(client):
    response = client.get("/api/v1/notifications/stats")
    assert response.status_code == 200

    assert response.get_json() == {
        "ok": True,
        "total_notifications": 3,
        "unread_count": 2,
        "by_source": {
            "presence": 1,
            "dashboard_layout": 1,
            "zone_truth": 1,
        },
        "by_priority": {
            "high": 1,
            "normal": 1,
            "low": 1,
        },
        "by_type": {
            "alert": 1,
            "info": 1,
            "suggestion": 1,
        },
    }


def test_notifications_pending_contract_exposes_minimal_delivery_queue_follow_up_slice(client):
    response = client.get("/api/v1/notifications/pending")
    assert response.status_code == 200

    assert response.get_json() == {
        "ok": True,
        "count": 2,
        "pending": [
            {
                "id": "pending_presence_hold_office_push",
                "notification_id": "notif_presence_hold_office",
                "title": "Presence Hold aktiv",
                "message": "Push-Auslieferung an die Haushaltsgeräte steht noch aus.",
                "priority": "high",
                "type": "alert",
                "source": "presence",
                "queued_at": "2026-04-08T04:41:00+00:00",
                "scheduled_for": "2026-04-08T04:45:00+00:00",
                "channels": ["push", "telegram"],
                "retry_count": 1,
            },
            {
                "id": "pending_zone_catalog_review_digest",
                "notification_id": "notif_zone_catalog_review",
                "title": "Zone-Katalog prüfen",
                "message": "Der nächste Digest-Eintrag für die Zonenprüfung ist noch zur Auslieferung vorgemerkt.",
                "priority": "low",
                "type": "suggestion",
                "source": "zone_truth",
                "queued_at": "2026-04-08T04:18:00+00:00",
                "scheduled_for": "2026-04-08T05:00:00+00:00",
                "channels": ["digest"],
                "retry_count": 0,
            },
        ],
    }
