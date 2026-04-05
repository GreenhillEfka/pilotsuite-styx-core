from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import backend_ui as module  # noqa: E402


class FakeZone:
    def __init__(
        self,
        enabled_modules: set[str] | None = None,
        *,
        zone_type: str = "living",
    ) -> None:
        self.enabled_modules = set(enabled_modules or set())
        self.zone_type = zone_type


class FakeEngine:
    def __init__(
        self,
        *,
        overview: dict[str, object] | None = None,
        zone_payloads: dict[str, dict[str, object]] | None = None,
        zones: dict[str, FakeZone] | None = None,
    ) -> None:
        self._overview = overview or {
            "zones": [{"zone_id": "living", "name": "Wohnzimmer", "zone_type": "living"}],
            "total_zones": 1,
        }
        self._zone_payloads = zone_payloads or {
            "living": {
                "zone_id": "living",
                "name": "Wohnzimmer",
                "zone_type": "living",
                "enabled_modules": ["presence"],
                "entities": ["light.living_main", "climate.living"],
            }
        }
        self._zones = zones or {"living": FakeZone({"presence"}, zone_type="living")}

    def get_overview(self) -> dict[str, object]:
        return self._overview

    def get_zone(self, zone_id: str):
        return self._zone_payloads.get(zone_id)


class FakeRegistry:
    def __init__(
        self,
        *,
        global_states: dict[str, str] | None = None,
        zone_states: dict[str, dict[str, str]] | None = None,
        set_state_result: bool = True,
    ) -> None:
        self.global_states = dict(global_states or {})
        self.zone_states = {
            zone_id: dict(module_states)
            for zone_id, module_states in (zone_states or {}).items()
        }
        self.set_state_result = set_state_result
        self.events: list[tuple[str, str, str | None, str | None]] = []
        self.state_events: list[tuple[str, str, str]] = []

    def get_state(self, module_id: str) -> str:
        return self.global_states.get(module_id, "active")

    def set_state(self, module_id: str, state: str) -> bool:
        self.state_events.append(("set", module_id, state))
        if not self.set_state_result:
            return False
        self.global_states[module_id] = state
        return True

    def get_zone_states(self, zone_id: str) -> dict[str, str]:
        return dict(self.zone_states.get(zone_id, {}))

    def get_all_states(self) -> dict[str, str]:
        return dict(self.global_states)

    def get_all_zone_states(self) -> dict[str, dict[str, str]]:
        return {
            zone_id: dict(module_states)
            for zone_id, module_states in self.zone_states.items()
        }

    def set_zone_state(self, zone_id: str, module_id: str, state: str) -> bool:
        self.zone_states.setdefault(zone_id, {})[module_id] = state
        self.events.append(("set", zone_id, module_id, state))
        return True

    def delete_zone_state(self, zone_id: str, module_id: str) -> bool:
        zone_overrides = self.zone_states.setdefault(zone_id, {})
        existed = module_id in zone_overrides
        zone_overrides.pop(module_id, None)
        self.events.append(("delete", zone_id, module_id, None))
        return existed


def _build_client(
    monkeypatch,
    *,
    has_engine: bool = True,
    overview: dict[str, object] | None = None,
    zone_payloads: dict[str, dict[str, object]] | None = None,
    zones: dict[str, FakeZone] | None = None,
    sync_result: bool = True,
    global_states: dict[str, str] | None = None,
    zone_states: dict[str, dict[str, str]] | None = None,
    set_state_result: bool = True,
):
    engine = FakeEngine(overview=overview, zone_payloads=zone_payloads, zones=zones)
    registry = FakeRegistry(
        global_states=global_states,
        zone_states=zone_states,
        set_state_result=set_state_result,
    )

    monkeypatch.setattr(module, "HAS_ENGINE", has_engine)
    monkeypatch.setattr(module, "_get_module_registry", lambda: registry)
    if has_engine:
        monkeypatch.setattr(module, "HabitusZoneEngine", lambda: engine)
        monkeypatch.setattr(
            module,
            "_ZONE_TEMPLATES",
            {
                "living": {
                    "name": "Wohnzimmer",
                    "icon": "mdi:sofa",
                    "enabled_modules": ["presence", "light"],
                }
            },
        )
        monkeypatch.setattr(
            module,
            "_ZONE_MODES",
            {
                "relax": {
                    "name": "Relax",
                    "icon": "mdi:sofa-outline",
                    "automations": ["scene.relax"],
                }
            },
        )
        monkeypatch.setattr(module, "_sync_zone_module_state", lambda zone_id, module_id, state: sync_result)

    app = Flask(__name__)
    app.register_blueprint(module.backend_ui_bp)
    return app.test_client(), engine, registry


def test_backend_ui_static_surfaces_contract(monkeypatch) -> None:
    client, _engine, _registry = _build_client(
        monkeypatch,
        zone_payloads={
            "living": {
                "zone_id": "living",
                "name": "Wohnzimmer",
                "zone_type": "living",
                "enabled_modules": ["presence", "climate"],
                "entities": ["light.living_main", "climate.living"],
            }
        },
        zones={"living": FakeZone({"presence", "climate"}, zone_type="living")},
        global_states={"presence": "learning", "light": "off", "climate": "active"},
        zone_states={"living": {"light": "learning", "climate": "active"}},
    )

    response = client.get("/api/v1/backend/dashboard")
    assert response.status_code == 200
    dashboard = response.get_json()
    assert dashboard["system"]["status"] == "healthy"
    assert len(dashboard["quick_actions"]) == 3

    response = client.get("/api/v1/backend/modules")
    assert response.status_code == 200
    modules = response.get_json()
    modules_by_id = {item["module_id"]: item for item in modules["modules"]}
    assert [item["module_id"] for item in modules["modules"]] == ["presence", "light", "climate"]
    assert modules_by_id["presence"] == {
        "module_id": "presence",
        "name": "Presence Intelligence",
        "description": "Person-Tracking, Room-Transitions, Occupancy",
        "category": "domain",
        "state": "learning",
        "global_state": "learning",
        "config_schema": {
            "presence_hold_minutes": {"type": "int", "default": 5},
            "auto_off_minutes": {"type": "int", "default": 10},
        },
        "config": {
            "presence_hold_minutes": 5,
            "auto_off_minutes": 10,
        },
        "dependencies": [],
        "zones_enabled": 1,
        "zone_overrides": 0,
        "has_zone_overrides": False,
    }
    assert modules_by_id["light"] == {
        "module_id": "light",
        "name": "Light Intelligence",
        "description": "Adaptive Lighting, Scenes, Sun-Tracking",
        "category": "domain",
        "state": "off",
        "global_state": "off",
        "config_schema": {
            "scene_default": {"type": "string", "default": "relax"},
            "brightness_max": {"type": "int", "default": 100},
        },
        "config": {
            "scene_default": "relax",
            "brightness_max": 100,
        },
        "dependencies": ["presence", "timeofday"],
        "zones_enabled": 1,
        "zone_overrides": 1,
        "has_zone_overrides": True,
    }
    assert modules_by_id["climate"] == {
        "module_id": "climate",
        "name": "Climate",
        "description": "",
        "category": "domain",
        "state": "active",
        "global_state": "active",
        "config_schema": {},
        "config": {},
        "dependencies": [],
        "zones_enabled": 1,
        "zone_overrides": 1,
        "has_zone_overrides": True,
    }
    assert modules["states"][0]["id"] == "active"

    response = client.get("/api/v1/backend/brain")
    assert response.status_code == 200
    brain = response.get_json()
    # Slice 129: Graph stats are now dynamic from BrainGraphService (may be 0 in test env)
    assert "graph" in brain
    assert "nodes" in brain["graph"]
    assert "edges" in brain["graph"]
    assert isinstance(brain["graph"]["nodes"], int)
    assert isinstance(brain["graph"]["edges"], int)
    assert brain["pipeline"]["suggestions_generated"] == 3

    response = client.get("/api/v1/backend/mood")
    assert response.status_code == 200
    mood = response.get_json()
    assert mood["current"]["state"] == "relax"
    assert len(mood["states"]) == 6

    response = client.get("/api/v1/backend/automation")
    assert response.status_code == 200
    automation = response.get_json()
    assert automation["proposals"][0]["status"] == "pending"
    assert automation["rules"][0]["active"] is True

    response = client.post("/api/v1/backend/automation/proposals/prop_001/accept")
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "proposal_id": "prop_001", "action": "accepted"}

    response = client.post("/api/v1/backend/automation/proposals/prop_001/reject")
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "proposal_id": "prop_001", "action": "rejected"}

    response = client.get("/api/v1/backend/rag")
    assert response.status_code == 200
    rag = response.get_json()
    assert rag["vectors"]["count"] == 1500
    assert rag["voice"]["model"] == "whisper"

    response = client.get("/api/v1/backend/media")
    assert response.status_code == 200
    media = response.get_json()
    assert media["sonos"]["players"][0]["zone"] == "living"
    assert media["musikwolke"]["enabled"] is True

    response = client.get("/api/v1/backend/hardware")
    assert response.status_code == 200
    hardware = response.get_json()
    assert hardware["zigbee"]["status"] == "online"
    assert hardware["cameras"][0]["id"] == "cam_001"

    response = client.get("/api/v1/backend/system")
    assert response.status_code == 200
    system = response.get_json()
    assert system["health"]["uptime_hours"] == 48.5
    assert system["models"]["current"] == "qwen3.5:397b-cloud"


def test_backend_ui_zone_surfaces_and_tags_contract(monkeypatch) -> None:
    client, _engine, _registry = _build_client(
        monkeypatch,
        zones={"living": FakeZone({"presence", "climate"}, zone_type="living")},
        zone_payloads={
            "living": {
                "zone_id": "living",
                "name": "Wohnzimmer",
                "zone_type": "living",
                "enabled_modules": ["presence", "climate"],
                "entities": ["light.living_main", "climate.living"],
            }
        },
        global_states={"presence": "active", "light": "active", "climate": "active"},
        zone_states={"living": {"light": "off", "climate": "learning"}},
    )

    response = client.get("/api/v1/backend/zones")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["zones"] == [
        {
            "zone_id": "living",
            "name": "Wohnzimmer",
            "zone_type": "living",
            "enabled_modules": ["climate", "presence"],
            "modules": [
                {
                    "zone_id": "living",
                    "module_id": "climate",
                    "state": "learning",
                    "global_state": "active",
                    "override_state": "learning",
                    "has_override": True,
                },
                {
                    "zone_id": "living",
                    "module_id": "light",
                    "state": "off",
                    "global_state": "active",
                    "override_state": "off",
                    "has_override": True,
                },
                {
                    "zone_id": "living",
                    "module_id": "presence",
                    "state": "active",
                    "global_state": "active",
                    "override_state": None,
                    "has_override": False,
                },
            ],
        }
    ]
    assert payload["zone_types"] == [
        {
            "id": "living",
            "name": "Wohnzimmer",
            "icon": "mdi:sofa",
            "default_modules": ["presence", "light"],
        }
    ]
    assert payload["zone_modes"] == [
        {
            "id": "relax",
            "name": "Relax",
            "icon": "mdi:sofa-outline",
            "automations": ["scene.relax"],
        }
    ]
    assert payload["module_states"][2] == {
        "id": "off",
        "name": "Aus",
        "description": "Deaktiviert",
    }
    assert payload["overview"]["zones"] == payload["zones"]

    response = client.get("/api/v1/backend/zones/living/entities")
    assert response.status_code == 200
    entities = response.get_json()
    assert entities == {
        "zone_id": "living",
        "enabled_modules": ["climate", "presence"],
        "modules": [
            {
                "zone_id": "living",
                "module_id": "climate",
                "state": "learning",
                "global_state": "active",
                "override_state": "learning",
                "has_override": True,
            },
            {
                "zone_id": "living",
                "module_id": "light",
                "state": "off",
                "global_state": "active",
                "override_state": "off",
                "has_override": True,
            },
            {
                "zone_id": "living",
                "module_id": "presence",
                "state": "active",
                "global_state": "active",
                "override_state": None,
                "has_override": False,
            },
        ],
        "entities": [
            {
                "entity_id": "light.living_main",
                "domain": "light",
                "tags": ["domain:light", "zone_living", "auto_assign"],
            },
            {
                "entity_id": "climate.living",
                "domain": "climate",
                "tags": ["domain:climate", "zone_living", "auto_assign"],
            },
        ],
        "tag_categories": [
            {
                "id": "domain",
                "name": "Domain",
                "values": ["light", "climate", "motion", "media", "sensor", "switch", "camera", "cover", "lock"],
            },
            {
                "id": "zone",
                "name": "Zone",
                "values": ["zone_living"],
            },
            {
                "id": "status",
                "name": "Status",
                "values": ["auto_assign", "needs_review", "manual_override"],
            },
        ],
    }

    response = client.get("/api/v1/backend/zones/missing/entities")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Zone missing not found"}


def test_backend_ui_zone_module_mutation_validation_and_sync_reporting(monkeypatch) -> None:
    zones = {
        "living": FakeZone({"presence"}),
        "sleep": FakeZone({"light"}),
    }
    client, engine, registry = _build_client(
        monkeypatch,
        zones=zones,
        sync_result=False,
        global_states={"light": "active", "climate": "learning"},
        zone_states={"living": {"light": "off"}},
    )

    response = client.post("/api/v1/backend/zones/living/modules")
    assert response.status_code == 400
    assert response.get_json() == {"error": "No JSON body provided"}

    response = client.post("/api/v1/backend/zones/living/modules", json={"state": "active"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing 'module_id'"}

    response = client.post(
        "/api/v1/backend/zones/living/modules",
        json={"module_id": "light", "state": "invalid"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid state. Must be one of: ['active', 'learning', 'off']"}

    response = client.post(
        "/api/v1/backend/zones/unknown/modules",
        json={"module_id": "light", "state": "active"},
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "Zone unknown not found"}

    response = client.post(
        "/api/v1/backend/zones/living/modules",
        json={"module_id": " light ", "state": "active"},
    )
    assert response.status_code == 200
    result = response.get_json()
    assert result["success"] is True
    assert result["zone_id"] == "living"
    assert result["module_id"] == "light"
    assert result["state"] == "active"
    assert result["global_state"] == "active"
    assert result["override_state"] is None
    assert result["has_override"] is False
    assert result["zone_updated"] is True
    assert result["ha_synced"] is False
    # Slice 131: Audit fields (execution_id, provenance, versioning)
    assert "execution_id" in result
    assert "provenance" in result
    assert result["provenance"]["source_agent"] == "pilotclaw"
    assert "versioning" in result
    assert registry.events == [("delete", "living", "light", None)]
    assert registry.zone_states["living"] == {}
    # Registry is canonical truth - zone.enabled_modules is no longer shadow-written
    # Effective state for light in living zone: global "active" means module should be considered active
    # but enabled_modules on FakeZone is just a test mock that doesn't auto-update anymore
    # We verify via registry that the override was deleted
    assert "light" not in registry.zone_states.get("living", {})

    response = client.post(
        "/api/v1/backend/zones/sleep/modules",
        json={"module_id": "light", "state": "off"},
    )
    assert response.status_code == 200
    result2 = response.get_json()
    assert result2["success"] is True
    assert result2["zone_id"] == "sleep"
    assert result2["module_id"] == "light"
    assert result2["state"] == "off"
    assert result2["global_state"] == "active"
    assert result2["override_state"] == "off"
    assert result2["has_override"] is True
    assert result2["zone_updated"] is True
    assert result2["ha_synced"] is False
    assert "execution_id" in result2
    assert "provenance" in result2
    assert registry.events[-1] == ("set", "sleep", "light", "off")
    assert registry.zone_states["sleep"]["light"] == "off"
    # Registry has the override, zone.enabled_modules is deprecated for truth
    assert registry.zone_states["sleep"]["light"] == "off"

    response = client.post(
        "/api/v1/backend/zones/living/modules",
        json={"module_id": " climate ", "state": "off"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "zone_id": "living",
        "module_id": "climate",
        "state": "off",
        "global_state": "learning",
        "override_state": "off",
        "has_override": True,
        "zone_updated": True,
        "ha_synced": False,
    }
    assert registry.events[-1] == ("set", "living", "climate", "off")


def test_backend_ui_missing_engine_returns_503(monkeypatch) -> None:
    client, _engine, _registry = _build_client(monkeypatch, has_engine=False)

    response = client.get("/api/v1/backend/zones")
    assert response.status_code == 503
    assert response.get_json() == {"error": "HubZoneEngine not available"}

    response = client.get("/api/v1/backend/zones/living/entities")
    assert response.status_code == 503
    assert response.get_json() == {"error": "HubZoneEngine not available"}

    response = client.post(
        "/api/v1/backend/zones/living/modules",
        json={"module_id": "light", "state": "active"},
    )
    assert response.status_code == 503
    assert response.get_json() == {"error": "HubZoneEngine not available"}


def test_backend_ui_module_and_model_update_validation_contracts(monkeypatch) -> None:
    client, _engine, registry = _build_client(monkeypatch)

    response = client.put("/api/v1/backend/modules/presence")
    assert response.status_code == 400
    assert response.get_json() == {"error": "No JSON body provided"}

    response = client.put("/api/v1/backend/modules/presence", json={"state": "bad"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid state. Must be one of: ['active', 'learning', 'off']"}

    response = client.put("/api/v1/backend/modules/presence", json={"config": []})
    assert response.status_code == 400
    assert response.get_json() == {"error": "'config' must be an object"}

    response = client.put("/api/v1/backend/modules/presence", json={"notes": "ignored"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "No updatable fields provided"}

    response = client.put(
        "/api/v1/backend/modules/presence",
        json={"state": "learning", "config": {"presence_hold_minutes": 7}},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "module_id": "presence",
        "updated_fields": ["state", "config"],
    }
    assert registry.global_states["presence"] == "learning"
    assert registry.state_events == [("set", "presence", "learning")]

    response = client.get("/api/v1/backend/modules")
    assert response.status_code == 200
    modules_payload = response.get_json()
    modules_by_id = {item["module_id"]: item for item in modules_payload["modules"]}
    assert modules_by_id["presence"]["state"] == "learning"
    assert modules_by_id["presence"]["global_state"] == "learning"

    response = client.put("/api/v1/backend/system/models")
    assert response.status_code == 400
    assert response.get_json() == {"error": "No JSON body provided"}

    response = client.put("/api/v1/backend/system/models", json={"model_id": "   "})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing 'model_id'"}

    response = client.put("/api/v1/backend/system/models", json={"model_id": " glm-5:cloud "})
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "model_id": "glm-5:cloud"}


def test_backend_ui_module_update_surfaces_registry_write_failure(monkeypatch) -> None:
    client, _engine, registry = _build_client(monkeypatch, set_state_result=False)

    response = client.put("/api/v1/backend/modules/presence", json={"state": "off"})
    assert response.status_code == 500
    assert response.get_json() == {"error": "Failed to update module state for 'presence'"}
    assert registry.state_events == [("set", "presence", "off")]
    assert registry.global_states == {}
