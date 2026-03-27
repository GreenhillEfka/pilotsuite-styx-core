"""Regression coverage for zone truth sync metadata persistence."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.zone_automation import init_zone_automation_api, sync_zone_definitions  # noqa: E402
from copilot_core.hub.habitus_zones import HabitusZoneEngine  # noqa: E402
from copilot_core.hub.zone_automation import ZoneAutomationConfig, ZoneAutomationController  # noqa: E402


def test_zone_automation_config_roundtrips_zone_truth_metadata() -> None:
    cfg = ZoneAutomationConfig(
        zone_id="terrace",
        zone_name="Terrasse",
        zone_type="terrace",
        enabled_modules={"light", "camera", "music"},
        ha_entities=[{"entity_id": "light.balkon_licht", "role": "lights"}],
    )

    payload = cfg.to_dict()
    restored = ZoneAutomationConfig.from_dict(payload)

    assert payload["zone_type"] == "terrace"
    assert payload["enabled_modules"] == ["camera", "light", "music"]
    assert payload["ha_entities"] == [{"entity_id": "light.balkon_licht", "role": "lights"}]
    assert restored.zone_type == "terrace"
    assert restored.enabled_modules == {"light", "camera", "music"}
    assert restored.ha_entities == [{"entity_id": "light.balkon_licht", "role": "lights"}]
    assert restored._ha_entities == restored.ha_entities


def test_sync_definitions_persists_zone_truth_metadata_on_controller() -> None:
    controller = ZoneAutomationController()
    zone_engine = HabitusZoneEngine()
    init_zone_automation_api(controller, zone_engine)

    app = Flask(__name__)
    app.config["TESTING"] = True

    payload = {
        "source": "ha",
        "zones": [
            {
                "zone_id": "terrace",
                "name_de": "Terrasse",
                "zone_type": "terrace",
                "enabled_modules": ["light", "camera", "music"],
                "entities": [
                    {"entity_id": "light.balkon_licht", "role": "lights"},
                    {"entity_id": "camera.terrasse", "role": "camera"},
                ],
            }
        ],
    }

    with app.test_request_context(
        "/api/v1/zone-automation/sync-definitions",
        method="POST",
        json=payload,
    ):
        response = sync_zone_definitions.__wrapped__()

    body = response.get_json()
    cfg = controller.get_zone_config("terrace")
    zone = zone_engine.get_zone("terrace")

    assert body == {"ok": True, "synced": ["terrace"], "count": 1}
    assert cfg.zone_name == "Terrasse"
    assert cfg.zone_type == "terrace"
    assert cfg.enabled_modules == {"light", "camera", "music"}
    assert cfg.ha_entities == [
        {"entity_id": "light.balkon_licht", "role": "lights"},
        {"entity_id": "camera.terrasse", "role": "camera"},
    ]
    assert cfg._ha_entities == cfg.ha_entities
    by_role = controller.get_zone_entities_by_role("terrace")
    assert set(by_role) == {"lights", "camera"}
    assert by_role["lights"][0]["entity_id"] == "light.balkon_licht"
    assert by_role["lights"][0]["role"] == "lights"
    assert by_role["lights"][0]["source"] == "ha_sync"
    assert "licht" in by_role["lights"][0]["tags"]
    assert by_role["camera"][0]["entity_id"] == "camera.terrasse"
    assert by_role["camera"][0]["role"] == "camera"
    assert by_role["camera"][0]["source"] == "ha_sync"
    assert zone is not None
    assert zone["name"] == "Terrasse"
    assert zone["zone_type"] == "terrace"
    assert zone["enabled_modules"] == ["camera", "light", "music"]
    assert zone["entities"] == ["light.balkon_licht", "camera.terrasse"]
