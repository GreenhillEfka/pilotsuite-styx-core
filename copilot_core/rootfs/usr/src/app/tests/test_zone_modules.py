"""Tests for zone_modules — Module-per-Zone architecture."""
from __future__ import annotations

import pytest
from flask import Flask

from copilot_core.hub.zone_modules import ZoneModuleRegistry, ZoneModuleFieldSpec
from copilot_core.hub.zone_modules.base import ZoneModuleConfig
from copilot_core.hub.zone_modules.registry import zone_module


class TestZoneModuleRegistry:
    """Test module registration and schema generation."""

    def test_ensure_loaded_registers_all_modules(self):
        ZoneModuleRegistry.ensure_loaded()
        modules = ZoneModuleRegistry.get_all()
        assert len(modules) >= 7
        assert "light" in modules
        assert "music" in modules
        assert "climate" in modules
        assert "cover" in modules
        assert "energy" in modules
        assert "scene" in modules
        assert "security" in modules

    def test_get_module_by_id(self):
        ZoneModuleRegistry.ensure_loaded()
        light = ZoneModuleRegistry.get("light")
        assert light is not None
        assert light.MODULE_ID == "light"
        assert light.MODULE_NAME_DE == "Lichtsteuerung"

    def test_get_nonexistent_module(self):
        assert ZoneModuleRegistry.get("nonexistent") is None

    def test_get_all_schemas(self):
        ZoneModuleRegistry.ensure_loaded()
        schemas = ZoneModuleRegistry.get_all_schemas()
        assert "light" in schemas
        assert "fields" in schemas["light"]
        assert len(schemas["light"]["fields"]) >= 10
        assert schemas["light"]["icon"] == "mdi:lightbulb"
        assert schemas["light"]["color"] == "#fbbf24"

    def test_create_defaults(self):
        ZoneModuleRegistry.ensure_loaded()
        defaults = ZoneModuleRegistry.create_defaults()
        assert "light" in defaults
        assert defaults["light"].enabled is True
        assert defaults["climate"].target_temp_c == 21.0

    def test_from_dict_round_trip(self):
        ZoneModuleRegistry.ensure_loaded()
        defaults = ZoneModuleRegistry.create_defaults()
        # Serialize
        data = {mid: mod.to_dict() for mid, mod in defaults.items()}
        # Deserialize
        restored = ZoneModuleRegistry.from_dict(data)
        assert set(restored.keys()) == set(defaults.keys())
        for mid in defaults:
            assert restored[mid].to_dict() == defaults[mid].to_dict()


class TestModuleConfigs:
    """Test individual module configurations."""

    def test_light_field_specs(self):
        ZoneModuleRegistry.ensure_loaded()
        light_cls = ZoneModuleRegistry.get("light")
        specs = light_cls.get_field_specs()
        keys = [s.key for s in specs]
        assert "enabled" in keys
        assert "brightness_target_pct" in keys
        assert "color_temp_k" in keys
        assert "mood_aware_enabled" in keys

    def test_music_field_specs(self):
        ZoneModuleRegistry.ensure_loaded()
        music_cls = ZoneModuleRegistry.get("music")
        specs = music_cls.get_field_specs()
        keys = [s.key for s in specs]
        assert "enabled" in keys
        assert "default_volume_pct" in keys
        assert "follow_mode" in keys

    def test_climate_defaults(self):
        ZoneModuleRegistry.ensure_loaded()
        cls = ZoneModuleRegistry.get("climate")
        inst = cls()
        assert inst.target_temp_c == 21.0
        assert inst.night_setback_c == 18.0
        assert inst.window_off is True

    def test_cover_defaults(self):
        ZoneModuleRegistry.ensure_loaded()
        cls = ZoneModuleRegistry.get("cover")
        inst = cls()
        assert inst.sun_protection is True
        assert inst.default_position_pct == 100

    def test_energy_defaults(self):
        ZoneModuleRegistry.ensure_loaded()
        cls = ZoneModuleRegistry.get("energy")
        inst = cls()
        assert inst.standby_detection is True
        assert inst.standby_threshold_w == 5.0

    def test_security_defaults(self):
        ZoneModuleRegistry.ensure_loaded()
        cls = ZoneModuleRegistry.get("security")
        inst = cls()
        assert inst.auto_lock is False
        assert inst.alert_open_window is True

    def test_from_dict_partial(self):
        ZoneModuleRegistry.ensure_loaded()
        cls = ZoneModuleRegistry.get("climate")
        inst = cls.from_dict({"target_temp_c": 23.0})
        assert inst.target_temp_c == 23.0
        assert inst.enabled is True  # default preserved

    def test_matches_entity_by_domain(self):
        ZoneModuleRegistry.ensure_loaded()
        cls = ZoneModuleRegistry.get("light")
        assert cls.matches_entity("light.wohnzimmer") is True
        assert cls.matches_entity("climate.bad") is False

    def test_matches_entity_by_role(self):
        ZoneModuleRegistry.ensure_loaded()
        cls = ZoneModuleRegistry.get("climate")
        assert cls.matches_entity("sensor.temp", role="climate") is True
        assert cls.matches_entity("sensor.temp", role="lights") is False

    def test_matches_entity_by_tag(self):
        ZoneModuleRegistry.ensure_loaded()
        cls = ZoneModuleRegistry.get("security")
        assert cls.matches_entity("binary_sensor.x", tags=["schloss"]) is True
        assert cls.matches_entity("binary_sensor.x", tags=["licht"]) is False


class TestZoneAutomationWithModules:
    """Test ZoneAutomationConfig with the modules dict."""

    def test_config_creates_modules(self):
        from copilot_core.hub.zone_automation import ZoneAutomationConfig
        cfg = ZoneAutomationConfig(zone_id="test")
        assert "light" in cfg.modules
        assert "climate" in cfg.modules
        assert len(cfg.modules) >= 7

    def test_config_to_dict_has_modules(self):
        from copilot_core.hub.zone_automation import ZoneAutomationConfig
        cfg = ZoneAutomationConfig(zone_id="test")
        d = cfg.to_dict()
        assert "modules" in d
        assert "light" in d["modules"]
        assert "climate" in d["modules"]
        # Legacy keys preserved
        assert "light" in d
        assert "music" in d

    def test_config_from_dict_with_modules(self):
        from copilot_core.hub.zone_automation import ZoneAutomationConfig
        data = {
            "zone_id": "test",
            "modules": {
                "climate": {"target_temp_c": 25.0},
            },
        }
        cfg = ZoneAutomationConfig.from_dict(data)
        assert cfg.modules["climate"].target_temp_c == 25.0

    def test_set_zone_config_updates_modules(self):
        from copilot_core.hub.zone_automation import ZoneAutomationController
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("wohnbereich", {
            "modules": {"climate": {"target_temp_c": 22.0}},
        })
        cfg = ctrl.get_zone_config("wohnbereich")
        assert cfg.modules["climate"].target_temp_c == 22.0


class TestModuleSchemasAPI:
    """Test the module-schemas API endpoint."""

    def test_get_module_schemas(self):
        from copilot_core.api.v1.zone_automation import zone_automation_bp, init_zone_automation_api
        from copilot_core.hub.zone_automation import ZoneAutomationController

        app = Flask(__name__)
        app.register_blueprint(zone_automation_bp)
        ctrl = ZoneAutomationController()
        init_zone_automation_api(ctrl)

        with app.test_client() as c:
            resp = c.get("/api/v1/zone-automation/module-schemas")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert "light" in data["schemas"]
            assert "climate" in data["schemas"]
            assert "fields" in data["schemas"]["light"]

    def test_get_zone_module_config(self):
        from copilot_core.api.v1.zone_automation import zone_automation_bp, init_zone_automation_api
        from copilot_core.hub.zone_automation import ZoneAutomationController

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(zone_automation_bp)
        ctrl = ZoneAutomationController()
        ctrl.get_zone_config("wohnbereich")  # ensure zone exists
        init_zone_automation_api(ctrl)

        with app.test_client() as c:
            resp = c.get("/api/v1/zone-automation/zones/wohnbereich/modules/climate")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["module_id"] == "climate"
            assert "target_temp_c" in data["config"]

    def test_set_zone_module_config(self):
        from copilot_core.api.v1.zone_automation import zone_automation_bp, init_zone_automation_api
        from copilot_core.hub.zone_automation import ZoneAutomationController

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(zone_automation_bp)
        ctrl = ZoneAutomationController()
        ctrl.get_zone_config("wohnbereich")
        init_zone_automation_api(ctrl)

        with app.test_client() as c:
            resp = c.post(
                "/api/v1/zone-automation/zones/wohnbereich/modules/climate",
                json={"target_temp_c": 24.5},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["config"]["target_temp_c"] == 24.5

    def test_get_zone_module_entities(self):
        from copilot_core.api.v1.zone_automation import zone_automation_bp, init_zone_automation_api
        from copilot_core.hub.zone_automation import ZoneAutomationController

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(zone_automation_bp)
        ctrl = ZoneAutomationController()
        ctrl.get_zone_config("wohnbereich")
        ctrl.add_entity("wohnbereich", "light.decke", role="lights")
        ctrl.add_entity("wohnbereich", "climate.heizung", role="climate")
        init_zone_automation_api(ctrl)

        with app.test_client() as c:
            # Light module entities
            resp = c.get("/api/v1/zone-automation/zones/wohnbereich/modules/light/entities")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["count"] == 1
            assert data["entities"][0]["entity_id"] == "light.decke"

            # Climate module entities
            resp = c.get("/api/v1/zone-automation/zones/wohnbereich/modules/climate/entities")
            data = resp.get_json()
            assert data["count"] == 1
            assert data["entities"][0]["entity_id"] == "climate.heizung"
