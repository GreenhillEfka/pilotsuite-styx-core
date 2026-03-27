"""Regression coverage for truth-backed dashboard read models."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.core.dashboard_read_models import (  # noqa: E402
    ModuleReadModel,
    ReadModelMeta,
    SystemOverviewReadModel,
    ZoneDetailReadModel,
    ZoneSummaryReadModel,
    build_system_overview_read_model,
)


class StubZoneEngine:
    """Minimal engine stub exposing the get_overview/get_zone contract."""

    def __init__(self, zones: list[dict], *, total_entities: int, active_zones: int) -> None:
        self._zones = {zone["zone_id"]: zone for zone in zones}
        self._overview = SimpleNamespace(
            zones=zones,
            total_zones=len(zones),
            total_entities=total_entities,
            active_zones=active_zones,
        )

    def get_overview(self):
        return self._overview

    def get_zone(self, zone_id: str):
        return self._zones.get(zone_id)

    def get_zone_state(self, zone_id: str):
        zone = self._zones.get(zone_id)
        if not zone:
            return None
        return SimpleNamespace(
            avg_temperature=zone.get("state", {}).get("avg_temperature"),
            avg_humidity=zone.get("state", {}).get("avg_humidity"),
            occupancy=zone.get("state", {}).get("occupancy", False),
            light_on_count=zone.get("state", {}).get("light_on_count", 0),
            active_devices=zone.get("state", {}).get("active_devices", 0),
        )


def test_zone_summary_counts_zone_types_not_modes() -> None:
    engine = StubZoneEngine(
        zones=[
            {
                "zone_id": "zone:living",
                "name": "Wohnbereich",
                "zone_type": "living",
                "icon": "mdi:sofa",
                "mode": "sleeping",
                "enabled": True,
                "room_count": 2,
                "entity_count": 5,
                "priority": 10,
            },
            {
                "zone_id": "zone:bath",
                "name": "Badbereich",
                "zone_type": "bath",
                "icon": "mdi:shower",
                "mode": "active",
                "enabled": True,
                "room_count": 1,
                "entity_count": 3,
                "priority": 5,
            },
        ],
        total_entities=8,
        active_zones=2,
    )

    model = ZoneSummaryReadModel.from_habitus_zones(engine)

    assert model.total_zones == 2
    assert model.total_entities == 8
    assert model.zone_types == {"living": 1, "bath": 1}
    assert [zone["zone_type"] for zone in model.zones] == ["living", "bath"]
    assert [zone["mode"] for zone in model.zones] == ["sleeping", "active"]


def test_zone_summary_example_data_preserves_display_zone_types() -> None:
    example_data = {
        "zone_entities": {
            "wohnbereich": {"lights": ["light.main"]},
            "badbereich": {"motion": ["binary_sensor.bad_motion"]},
        },
        "zone_display": {
            "wohnbereich": {
                "name": "Wohnbereich",
                "icon": "mdi:sofa",
                "zone_type": "living",
                "enabled_modules": ["light", "motion"],
            },
            "badbereich": {
                "name": "Badbereich",
                "icon": "mdi:shower",
                "zone_type": "bath",
                "enabled_modules": ["light", "climate"],
            },
        },
    }

    model = ZoneSummaryReadModel.from_habitus_zones(None, example_data=example_data)

    assert model.total_zones == 2
    assert model.active_zones == 2
    assert model.zone_types == {"living": 1, "bath": 1}
    assert model.zones[0]["zone_type"] == "living"
    assert model.zones[1]["zone_type"] == "bath"


def test_zone_detail_read_model_preserves_enabled_modules_from_zone_truth() -> None:
    engine = StubZoneEngine(
        zones=[
            {
                "zone_id": "zone:terrace",
                "name": "Terrasse",
                "zone_type": "terrace",
                "icon": "mdi:balcony",
                "mode": "active",
                "enabled": True,
                "priority": 7,
                "enabled_modules": ["camera", "light", "music"],
                "entity_count": 3,
                "room_count": 1,
                "entities": ["light.balkon_licht", "camera.terrasse", "media_player.terrasse"],
                "state": {
                    "avg_temperature": 18.2,
                    "avg_humidity": 55.0,
                    "occupancy": True,
                    "light_on_count": 1,
                    "active_devices": 2,
                },
            }
        ],
        total_entities=3,
        active_zones=1,
    )

    class _ModuleCfg:
        def __init__(self, payload):
            self._payload = payload

        def to_dict(self):
            return dict(self._payload)

    zone_automation = SimpleNamespace(
        get_zone_config=lambda zone_id: SimpleNamespace(
            modules={
                "camera": _ModuleCfg({"enabled": True, "capture_mode": "event"}),
                "light": _ModuleCfg({"enabled": True, "brightness_target_pct": 70}),
                "music": _ModuleCfg({"enabled": False, "follow_mode": True}),
                "climate": _ModuleCfg({"enabled": True, "target_temp_c": 21.0}),
            }
        )
    )

    model = ZoneDetailReadModel.from_habitus_zone(engine, "zone:terrace", zone_automation=zone_automation)

    assert model is not None
    assert model.zone_type == "terrace"
    assert model.enabled_modules == ["camera", "light", "music"]
    assert model.entities_by_role == {
        "lights": ["light.balkon_licht"],
        "camera": ["camera.terrasse"],
        "media": ["media_player.terrasse"],
    }
    assert model.modules == {
        "camera": {"enabled": True, "capture_mode": "event"},
        "light": {"enabled": True, "brightness_target_pct": 70},
        "music": {"enabled": False, "follow_mode": True},
    }
    assert "climate" not in model.modules
    assert model.state["avg_temperature"] == 18.2


def test_system_overview_default_nested_models_are_safe() -> None:
    overview = SystemOverviewReadModel(meta=ReadModelMeta(source="test"))

    payload = overview.to_dict()

    assert payload["source"] == "test"
    assert payload["zones"]["source"] == "system_overview.zones"
    assert payload["modules"]["source"] == "system_overview.modules"
    assert payload["zones"]["total_zones"] == 0
    assert payload["modules"]["modules"] == {}


def test_system_overview_read_model_preserves_zone_module_states() -> None:
    registry = SimpleNamespace(get_all_states=lambda: {"licht": "active", "heiz": "learning"})

    payload = build_system_overview_read_model(
        module_registry=registry,
        all_zone_states={
            "zone:living": {"licht": "active", "heiz": "learning"},
            "zone:office": {"licht": "off", "heiz": "off"},
        },
    )

    assert payload["modules"]["modules"] == {"licht": "active", "heiz": "learning"}
    assert payload["modules"]["by_zone"] == {
        "zone:living": {"licht": "active", "heiz": "learning"},
        "zone:office": {"licht": "off", "heiz": "off"},
    }
    assert payload["modules"]["zone_states"] == {"zone:living": "active", "zone:office": "off"}


def test_system_overview_can_derive_zone_module_states_from_automation_lane() -> None:
    class _ModuleCfg:
        def __init__(self, enabled: bool) -> None:
            self.enabled = enabled

    zone_automation = SimpleNamespace(
        _configs={
            "zone:living": SimpleNamespace(
                automation_mode="autonomy",
                enabled_modules={"licht", "musik"},
                modules={
                    "licht": _ModuleCfg(True),
                    "musik": _ModuleCfg(True),
                    "heiz": _ModuleCfg(True),
                },
            ),
            "zone:office": SimpleNamespace(
                automation_mode="learning",
                enabled_modules={"licht", "heiz"},
                modules={
                    "licht": _ModuleCfg(False),
                    "heiz": _ModuleCfg(True),
                },
            ),
        }
    )

    payload = build_system_overview_read_model(zone_automation=zone_automation)

    assert payload["modules"]["by_zone"] == {
        "zone:living": {"licht": "active", "musik": "active"},
        "zone:office": {"licht": "off", "heiz": "learning"},
    }
    assert payload["modules"]["zone_states"] == {"zone:living": "active", "zone:office": "off"}


def test_system_overview_brain_snapshot_accepts_to_dict_objects_and_adds_source() -> None:
    class _BrainSnapshot:
        def to_dict(self):
            return {
                "pipeline_version": "1.2.3",
                "graph": {"total_nodes": 9, "total_edges": 14},
            }

    payload = build_system_overview_read_model(brain_summary=_BrainSnapshot())

    assert payload["brain"]["pipeline_version"] == "1.2.3"
    assert payload["brain"]["graph"] == {"total_nodes": 9, "total_edges": 14}
    assert payload["brain"]["source"] == "brain_read_model"
    assert "generated_at" in payload["brain"]


def test_module_read_model_zone_states_can_resolve_off_as_dominant() -> None:
    model = ModuleReadModel.from_module_registry(
        registry=None,
        all_zone_states={
            "zone:office": {
                "licht": "off",
                "bewegung": "off",
                "heiz": "learning",
            }
        },
    )

    assert model.zone_states == {"zone:office": "off"}


def test_module_read_model_zone_states_keep_active_as_tie_breaker() -> None:
    model = ModuleReadModel.from_module_registry(
        registry=None,
        all_zone_states={
            "zone:living": {
                "licht": "active",
                "bewegung": "learning",
                "heiz": "active",
                "musik": "learning",
            }
        },
    )

    assert model.zone_states == {"zone:living": "active"}
