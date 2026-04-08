from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"))

from main import create_app


def test_presence_contract_exposes_minimal_read_only_household_summary():
    client = create_app({"TESTING": True}).test_client()

    response = client.get("/api/v1/presence")
    assert response.status_code == 200

    data = response.get_json()
    assert data == {
        "ok": True,
        "source": "static_presence_snapshot",
        "household_status": "partial",
        "persons_home": [
            {
                "icon": "mdi:account-circle",
                "name": "Andreas",
                "person_id": "person.andreas",
                "since": "2026-04-08T03:55:00+00:00",
                "state": "home",
                "updated_at": "2026-04-08T04:18:00+00:00",
                "zone": "office",
            },
            {
                "icon": "mdi:account",
                "name": "Mira",
                "person_id": "person.mira",
                "since": "2026-04-08T04:05:00+00:00",
                "state": "home",
                "updated_at": "2026-04-08T04:15:00+00:00",
                "zone": "room_mira",
            },
        ],
        "persons_away": [
            {
                "icon": "mdi:account",
                "name": "Paul",
                "person_id": "person.paul",
                "since": "2026-04-08T02:10:00+00:00",
                "state": "not_home",
                "updated_at": "2026-04-08T04:10:00+00:00",
                "zone": "",
            }
        ],
        "total_home": 2,
        "total_tracked": 3,
        "hold_active": {},
        "last_updated": "2026-04-08T04:18:00+00:00",
    }
