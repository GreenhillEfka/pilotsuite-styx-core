"""Regression coverage for Core wiring / startup contracts."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.core_setup import register_blueprints  # noqa: E402
from copilot_core.homeassistant.habitus_zones import ZoneType  # noqa: E402
from copilot_core.homeassistant.zone_matcher import map_homeassistant_topology  # noqa: E402


def test_core_setup_keeps_events_ingest_unprefixed_in_runtime_routes() -> None:
    app = Flask(__name__)
    register_blueprints(app, {})

    rules = {str(rule) for rule in app.url_map.iter_rules()}
    assert "/api/v1/events" in rules
    assert "/api/v1/events/stats" in rules
    assert "/api/v1/api/v1/events" not in rules
    assert "/api/v1/api/v1/events/stats" not in rules


def test_homeassistant_package_keeps_static_zone_modules_importable_without_runtime_client_deps() -> None:
    assert ZoneType.LIVING.value == "living"


def test_map_homeassistant_topology_returns_grouped_and_ungeordnet_data() -> None:
    payload = map_homeassistant_topology(
        areas=[
            {"area_id": "wohnzimmer", "name": "Wohnzimmer"},
            {"area_id": "atelier", "name": "Atelier Nord"},
        ],
        entities=[
            {
                "entity_id": "light.wohnzimmer_decke",
                "attributes": {"friendly_name": "Wohnzimmer Decke", "area_id": "wohnzimmer"},
            },
            {
                "entity_id": "sensor.mystery_probe",
                "attributes": {"friendly_name": "ZX Probe 9", "area_id": "atelier"},
            },
        ],
    )

    assert payload["summary"]["area_count"] == 2
    assert payload["summary"]["entity_count"] == 2
    assert payload["ungeordnet"]["entity_count"] == 1
    assert any(zone["zone_type"] == "living" for zone in payload["zones"])
