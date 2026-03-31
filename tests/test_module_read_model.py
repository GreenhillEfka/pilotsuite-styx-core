"""Tests for Module Read Model — First-class module state and config."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)

from copilot_core.core.module_read_model import (
    ModuleSnapshotV1,
    ModuleFieldStateV1,
    ModuleReadModel,
    build_module_read_model,
    get_module_read_model,
    update_module_state,
    get_module_state,
    get_all_module_states,
    reset_module_state,
)


class TestModuleFieldStateV1:
    """Tests for ModuleFieldStateV1 dataclass."""

    def test_create_field_state(self) -> None:
        """Test creating a field state."""
        fs = ModuleFieldStateV1(
            key="brightness_target_pct",
            value=80,
            field_type="int",
        )
        
        assert fs.key == "brightness_target_pct"
        assert fs.value == 80
        assert fs.field_type == "int"

    def test_field_state_to_dict(self) -> None:
        """Test field state serialization."""
        fs = ModuleFieldStateV1(
            key="enabled",
            value=True,
            field_type="bool",
        )
        
        data = fs.to_dict()
        assert data["key"] == "enabled"
        assert data["value"] is True
        assert data["field_type"] == "bool"
        assert "last_update" in data


class TestModuleSnapshotV1:
    """Tests for ModuleSnapshotV1 dataclass."""

    def test_create_module_snapshot(self) -> None:
        """Test creating a module snapshot."""
        snapshot = ModuleSnapshotV1(
            module_id="light",
            module_name_de="Lichtsteuerung",
            module_icon="mdi:lightbulb",
            module_color="#fbbf24",
        )
        
        assert snapshot.module_id == "light"
        assert snapshot.module_name_de == "Lichtsteuerung"
        assert snapshot.module_icon == "mdi:lightbulb"
        assert snapshot.module_color == "#fbbf24"
        assert snapshot.enabled is True
        assert snapshot.revision == 0

    def test_module_snapshot_with_config(self) -> None:
        """Test module snapshot with configuration."""
        snapshot = ModuleSnapshotV1(
            module_id="light",
            module_name_de="Lichtsteuerung",
            module_icon="mdi:lightbulb",
            module_color="#fbbf24",
            config={"brightness_target_pct": 75, "enabled": True},
        )
        
        assert snapshot.config["brightness_target_pct"] == 75
        assert snapshot.enabled is True

    def test_module_snapshot_touch(self) -> None:
        """Test revision increment on touch."""
        snapshot = ModuleSnapshotV1(
            module_id="light",
            module_name_de="Lichtsteuerung",
            module_icon="mdi:lightbulb",
            module_color="#fbbf24",
        )
        
        initial_revision = snapshot.revision
        snapshot.touch()
        
        assert snapshot.revision == initial_revision + 1

    def test_module_snapshot_update_state(self) -> None:
        """Test state update triggers revision."""
        snapshot = ModuleSnapshotV1(
            module_id="motion",
            module_name_de="Bewegungserkennung",
            module_icon="mdi:motion-sensor",
            module_color="#a78bfa",
        )
        
        initial_revision = snapshot.revision
        snapshot.update_state({"sensors_active": 3, "last_motion": "2026-03-31T10:00:00Z"})
        
        assert snapshot.revision > initial_revision
        assert snapshot.state_summary["sensors_active"] == 3

    def test_module_snapshot_to_dict(self) -> None:
        """Test full serialization."""
        snapshot = ModuleSnapshotV1(
            module_id="climate",
            module_name_de="Klimasteuerung",
            module_icon="mdi:thermometer",
            module_color="#34d399",
            config={"target_temp": 21.0},
            applicable_zones=["wohnzimmer", "schlafzimmer"],
            relevant_roles=["climate", "sensors"],
        )
        
        data = snapshot.to_dict()
        
        assert data["module_id"] == "climate"
        assert data["config"]["target_temp"] == 21.0
        assert "wohnzimmer" in data["applicable_zones"]
        assert "climate" in data["relevant_roles"]


class TestModuleReadModel:
    """Tests for ModuleReadModel."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_module_state()

    def test_empty_read_model(self) -> None:
        """Test read model with no data."""
        model = build_module_read_model()
        
        assert model.generated_at is not None
        assert len(model.modules) == 0
        assert len(model.zone_module_map) == 0
        assert model.summary["total_modules"] == 0

    def test_read_model_with_modules(self) -> None:
        """Test read model populated with module data."""
        # Pre-populate module state
        update_module_state(
            module_id="light",
            state_update={"lights_on": 5, "avg_brightness": 60},
            health="ok",
        )
        update_module_state(
            module_id="motion",
            state_update={"sensors_active": 2},
            health="ok",
        )
        
        model = build_module_read_model()
        
        assert "light" in model.modules
        assert "motion" in model.modules
        assert model.summary["total_modules"] == 2

    def test_read_model_to_dict(self) -> None:
        """Test read model serialization."""
        update_module_state(
            module_id="light",
            state_update={"lights_on": 3},
        )
        
        model = build_module_read_model()
        data = model.to_dict()
        
        assert "generated_at" in data
        assert "modules" in data
        assert "zone_module_map" in data
        assert "summary" in data
        assert "light" in data["modules"]


class TestModuleStateAPI:
    """Tests for module state update/query API."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_module_state()

    def test_update_and_get_module_state(self) -> None:
        """Test updating and retrieving module state."""
        update_module_state(
            module_id="heiz",
            state_update={"current_temp": 21.5, "target_temp": 22.0, "is_heating": True},
            health="ok",
            health_message="Normalbetrieb",
        )
        
        state = get_module_state("heiz")
        
        assert state is not None
        assert state["module_id"] == "heiz"
        assert state["state_summary"]["current_temp"] == 21.5
        assert state["health"] == "ok"

    def test_get_unknown_module_state(self) -> None:
        """Test retrieving state for unknown module."""
        state = get_module_state("unknown_module")
        
        assert state is None

    def test_get_all_module_states(self) -> None:
        """Test retrieving all module states."""
        update_module_state("light", {"lights_on": 2})
        update_module_state("climate", {"temp": 20.0})
        
        all_states = get_all_module_states()
        
        assert len(all_states) == 2
        assert "light" in all_states
        assert "climate" in all_states


class TestModuleReadModelIntegration:
    """Integration tests with mock services."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_module_state()

    def test_build_with_mock_registry(self) -> None:
        """Test building read model with mock module registry."""
        class MockRegistry:
            def get_all_schemas(self):
                return {
                    "light": {
                        "name_de": "Lichtsteuerung",
                        "icon": "mdi:lightbulb",
                        "color": "#fbbf24",
                        "relevant_roles": ["lights"],
                        "relevant_tags": ["licht"],
                        "relevant_domains": ["light"],
                    },
                    "climate": {
                        "name_de": "Klimasteuerung",
                        "icon": "mdi:thermometer",
                        "color": "#34d399",
                        "relevant_roles": ["climate"],
                        "relevant_tags": ["klima"],
                        "relevant_domains": ["climate"],
                    },
                }
        
        model = build_module_read_model(module_registry=MockRegistry())
        
        assert "light" in model.modules
        assert "climate" in model.modules
        assert model.modules["light"].module_name_de == "Lichtsteuerung"
        assert model.modules["climate"].module_icon == "mdi:thermometer"

    def test_build_with_mock_zone_controller(self) -> None:
        """Test building read model with mock zone automation controller."""
        class MockConfig:
            def __init__(self, zone_id, modules):
                self.zone_id = zone_id
                self._modules = modules
            
            def to_dict(self):
                return {"modules": self._modules}
        
        class MockController:
            def get_all_configs(self):
                return {
                    "wohnzimmer": MockConfig("wohnzimmer", {
                        "light": {"enabled": True, "brightness_target_pct": 80},
                        "climate": {"enabled": True, "target_temp": 21.0},
                    }),
                    "schlafzimmer": MockConfig("schlafzimmer", {
                        "light": {"enabled": False, "brightness_target_pct": 30},
                    }),
                }
        
        # First populate registry schemas
        class MockRegistry:
            def get_all_schemas(self):
                return {
                    "light": {"name_de": "Licht", "icon": "mdi:lightbulb", "color": "#fbbf24", "relevant_roles": ["lights"], "relevant_tags": [], "relevant_domains": []},
                    "climate": {"name_de": "Klima", "icon": "mdi:thermometer", "color": "#34d399", "relevant_roles": ["climate"], "relevant_tags": [], "relevant_domains": []},
                }
        
        model = build_module_read_model(
            module_registry=MockRegistry(),
            zone_automation_controller=MockController(),
        )
        
        # Check zone applicability
        assert "wohnzimmer" in model.modules["light"].applicable_zones
        assert "schlafzimmer" in model.modules["light"].applicable_zones
        assert "wohnzimmer" in model.modules["climate"].applicable_zones
        
        # Check zone_module_map
        assert "wohnzimmer" in model.zone_module_map
        assert "schlafzimmer" in model.zone_module_map
        assert "light" in model.zone_module_map["wohnzimmer"]
        assert "climate" in model.zone_module_map["wohnzimmer"]
