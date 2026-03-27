"""Contract coverage for zone dashboard ID normalization."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.zone_dashboard import (  # noqa: E402
    get_zone_detail,
    init_zone_dashboard_api,
    set_mood,
    zone_dashboard_bp,
)
from copilot_core.hub.habitus_zones import HabitusZoneEngine  # noqa: E402
from copilot_core.hub.zone_automation import ZoneAutomationController  # noqa: E402


def _init_services() -> tuple[HabitusZoneEngine, ZoneAutomationController]:
    zone_engine = HabitusZoneEngine()
    zone_engine.sync_external_zone_topology(
        "wohnbereich",
        name="Wohnbereich",
        zone_type="living",
        enabled_modules={"light", "motion"},
        entities=["light.living_room_main", "binary_sensor.living_room_motion"],
    )

    zone_automation = ZoneAutomationController()
    zone_automation.sync_entities_from_topology(
        "wohnbereich",
        [
            {"entity_id": "light.living_room_main", "role": "lights"},
            {"entity_id": "binary_sensor.living_room_motion", "role": "motion"},
        ],
    )

    init_zone_dashboard_api(habitus_zones=zone_engine, zone_automation=zone_automation)
    return zone_engine, zone_automation


def test_zone_dashboard_detail_accepts_unprefixed_truth_zone_id() -> None:
    _init_services()
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_dashboard_bp)

    with app.test_request_context("/api/v1/zone/dashboard/wohnbereich", method="GET"):
        response = get_zone_detail.__wrapped__("wohnbereich")

    body = response.get_json()
    assert body["ok"] is True
    assert body["zone"]["zone_id"] == "wohnbereich"
    assert body["zone"]["zone_type"] == "living"
    assert body["zone"]["entity_ids"] == ["light.living_room_main", "binary_sensor.living_room_motion"]


def test_zone_dashboard_mood_update_keeps_unprefixed_truth_zone_id() -> None:
    _init_services()
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_dashboard_bp)

    with app.test_request_context(
        "/api/v1/zone/dashboard/mood/wohnbereich",
        method="PUT",
        json={"comfort": 0.7, "joy": 0.6, "frugality": 0.4},
    ):
        response = set_mood.__wrapped__("wohnbereich")

    body = response.get_json()
    assert body["ok"] is True
    assert body["zone_id"] == "wohnbereich"
    assert body["mood"]["comfort"] == 0.7
