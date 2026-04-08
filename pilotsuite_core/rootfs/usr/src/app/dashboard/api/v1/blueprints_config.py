from __future__ import annotations

BLUEPRINT_CONTRACT_INVENTORY = [
    {
        "blueprint": "analytics_v1",
        "module": "dashboard.api.v1.analytics",
        "url_prefix": "/api/v1/analytics",
        "paths": {
            "/api/v1/analytics": ["get"],
        },
    },
    {
        "blueprint": "presence_v1",
        "module": "dashboard.api.v1.presence",
        "url_prefix": "/api/v1/presence",
        "paths": {
            "/api/v1/presence": ["get"],
        },
    },
    {
        "blueprint": "notifications_v1",
        "module": "dashboard.api.v1.notifications",
        "url_prefix": "/api/v1/notifications",
        "paths": {
            "/api/v1/notifications": ["get"],
            "/api/v1/notifications/digest": ["get"],
            "/api/v1/notifications/pending": ["get"],
            "/api/v1/notifications/stats": ["get"],
            "/api/v1/notifications/subscriptions": ["get"],
            "/api/v1/notifications/subscriptions/{device_id}": ["put"],
        },
    },
    {
        "blueprint": "zones_v1",
        "module": "dashboard.api.v1.zones",
        "url_prefix": "/api/v1/zones",
        "paths": {
            "/api/v1/zones": ["get"],
        },
    },
    {
        "blueprint": "widget_positions_v1",
        "module": "dashboard.api.v1.widget_positions",
        "url_prefix": "/api/v1/widgets/positions",
        "paths": {
            "/api/v1/widgets/positions": ["get", "post"],
            "/api/v1/widgets/positions/bulk": ["post"],
            "/api/v1/widgets/positions/{widget_id}": ["get", "delete"],
            "/api/v1/widgets/positions/{widget_id}/history": ["post"],
            "/api/v1/widgets/positions/{widget_id}/undo": ["post"],
            "/api/v1/widgets/positions/{widget_id}/redo": ["post"],
            "/api/v1/widgets/positions/reset": ["post"],
        },
    },
]
