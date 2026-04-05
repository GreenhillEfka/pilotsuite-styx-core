from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ps_core_runtime_contract_inventory.py"

spec = importlib.util.spec_from_file_location("ps_core_runtime_contract_inventory", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


CURRENT_RECOMMENDED_NEXT_SLICE = None


def test_runtime_contract_inventory_builds_from_active_worktree_truth() -> None:
    data = module.build_inventory(REPO_ROOT)

    assert data["summary"]["core_blueprint_entries"] >= 90
    assert data["summary"]["route_heavy_surfaces"] >= 20
    assert data["summary"]["route_heavy_without_direct_contract_tests"] == 0
    assert data["recommended_next_slice"] is CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_zone_editor_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    zone_editor = route_heavy["copilot_core.api.v1.zone_editor"]
    assert zone_editor["route_count"] >= 20
    assert "test_zone_editor_contract.py" in zone_editor["direct_contract_test_files"]
    assert "test_zone_editor_contract.py" in zone_editor["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.zone_editor" not in top_modules


def test_runtime_contract_inventory_marks_media_zones_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    media_zones = route_heavy["copilot_core.api.v1.media_zones"]
    assert media_zones["route_count"] >= 20
    assert "test_media_zones_contract.py" in media_zones["direct_contract_test_files"]
    assert "test_media_zones_contract.py" in media_zones["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.media_zones" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.media_zones"


def test_runtime_contract_inventory_marks_sonos_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    sonos = route_heavy["copilot_core.api.v1.sonos"]
    assert sonos["route_count"] >= 20
    assert "test_sonos_contract.py" in sonos["direct_contract_test_files"]
    assert "test_sonos_contract.py" in sonos["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.sonos" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.sonos"


def test_runtime_contract_inventory_marks_neurons_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    neurons = route_heavy["copilot_core.api.v1.neurons"]
    assert neurons["route_count"] >= 15
    assert "test_neurons_contract.py" in neurons["direct_contract_test_files"]
    assert "test_neurons_contract.py" in neurons["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.neurons" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.neurons"


def test_runtime_contract_inventory_marks_backend_ui_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    backend_ui = route_heavy["copilot_core.api.v1.backend_ui"]
    assert backend_ui["route_count"] >= 15
    assert "test_backend_ui_contract.py" in backend_ui["direct_contract_test_files"]
    assert "test_backend_ui_contract.py" in backend_ui["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.backend_ui" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.backend_ui"


def test_runtime_contract_inventory_marks_neurons_visualization_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    source_path = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.neurons_visualization")
    assert source_path is not None

    direct_tests, direct_contract_tests = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.neurons_visualization",
    )
    assert module.count_routes(source_path) == 3
    assert "test_neurons_visualization_contract.py" in direct_contract_tests
    assert "test_neurons_visualization_contract.py" in direct_tests
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.neurons_visualization"


def test_runtime_contract_inventory_marks_alarm_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    alarm = route_heavy["copilot_core.api.v1.alarm"]
    assert alarm["route_count"] >= 15
    assert "test_alarm_contract.py" in alarm["direct_contract_test_files"]
    assert "test_alarm_contract.py" in alarm["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.alarm" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.alarm"


def test_runtime_contract_inventory_marks_entity_adoption_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    entity_adoption = route_heavy["copilot_core.api.v1.entity_adoption"]
    assert entity_adoption["route_count"] >= 10
    assert "test_entity_adoption_contract.py" in entity_adoption["direct_contract_test_files"]
    assert "test_entity_adoption_contract.py" in entity_adoption["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.entity_adoption" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.entity_adoption"


def test_runtime_contract_inventory_marks_ha_module_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    ha_module = route_heavy["copilot_core.api.v1.ha_module"]
    assert ha_module["route_count"] >= 10
    assert "test_ha_module_contract.py" in ha_module["direct_contract_test_files"]
    assert "test_ha_module_contract.py" in ha_module["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.ha_module" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.ha_module"


def test_runtime_contract_inventory_marks_shopping_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    shopping = route_heavy["copilot_core.api.v1.shopping"]
    assert shopping["route_count"] >= 10
    assert "test_shopping_contract.py" in shopping["direct_contract_test_files"]
    assert "test_shopping_contract.py" in shopping["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.shopping" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.shopping"


def test_runtime_contract_inventory_marks_musikwolke_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    musikwolke = route_heavy["copilot_core.api.v1.musikwolke"]
    assert musikwolke["route_count"] >= 8
    assert "test_musikwolke_contract.py" in musikwolke["direct_contract_test_files"]
    assert "test_musikwolke_contract.py" in musikwolke["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.musikwolke" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.musikwolke"


def test_runtime_contract_inventory_marks_rag_ui_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    rag_ui = route_heavy["copilot_core.api.v1.rag_ui"]
    assert rag_ui["route_count"] >= 9
    assert "test_rag_ui_contract.py" in rag_ui["direct_contract_test_files"]
    assert "test_rag_ui_contract.py" in rag_ui["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.rag_ui" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.rag_ui"


def test_runtime_contract_inventory_marks_widget_positions_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    widget_positions = route_heavy["dashboard.api.v1.widget_positions"]
    assert widget_positions["route_count"] >= 8
    assert "test_widget_positions_contract.py" in widget_positions["direct_contract_test_files"]
    assert "test_widget_positions_contract.py" in widget_positions["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "dashboard.api.v1.widget_positions" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "dashboard.api.v1.widget_positions"


def test_runtime_contract_inventory_marks_reminders_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    reminders = route_heavy["copilot_core.api.v1.reminders"]
    assert reminders["route_count"] >= 7
    assert "test_reminders_contract.py" in reminders["direct_contract_test_files"]
    assert "test_reminders_contract.py" in reminders["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.reminders" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.reminders"


def test_runtime_contract_inventory_marks_module_control_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    module_control = route_heavy["copilot_core.api.v1.module_control"]
    assert module_control["route_count"] >= 6
    assert "test_module_control_contract.py" in module_control["direct_contract_test_files"]
    assert "test_module_control_contract.py" in module_control["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.module_control" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.module_control"


def test_runtime_contract_inventory_marks_ha_events_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    ha_events = route_heavy["copilot_core.api.v1.ha_events"]
    assert ha_events["route_count"] >= 8
    assert "test_ha_events_contract.py" in ha_events["direct_contract_test_files"]
    assert "test_ha_events_contract.py" in ha_events["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.ha_events" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.ha_events"


def test_runtime_contract_inventory_marks_neurons_ui_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    neurons_ui = route_heavy["copilot_core.api.v1.neurons_ui"]
    assert neurons_ui["route_count"] >= 8
    assert "test_neurons_ui_contract.py" in neurons_ui["direct_contract_test_files"]
    assert "test_neurons_ui_contract.py" in neurons_ui["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.neurons_ui" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.neurons_ui"


def test_runtime_contract_inventory_marks_autonomy_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    autonomy = route_heavy["copilot_core.api.v1.autonomy"]
    assert autonomy["route_count"] >= 7
    assert "test_autonomy_contract.py" in autonomy["direct_contract_test_files"]
    assert "test_autonomy_contract.py" in autonomy["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.autonomy" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.autonomy"


def test_runtime_contract_inventory_marks_user_hints_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    user_hints = route_heavy["copilot_core.api.v1.user_hints"]
    assert user_hints["route_count"] >= 7
    assert "test_user_hints_contract.py" in user_hints["direct_contract_test_files"]
    assert "test_user_hints_contract.py" in user_hints["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.user_hints" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.user_hints"


def test_runtime_contract_inventory_marks_rag_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    rag = route_heavy["copilot_core.api.v1.rag"]
    assert rag["route_count"] >= 8
    assert "test_rag_contract.py" in rag["direct_contract_test_files"]
    assert "test_rag_contract.py" in rag["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.rag" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.rag"


def test_runtime_contract_inventory_marks_neuron_layers_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    neuron_layers = route_heavy["copilot_core.api.v1.neuron_layers"]
    assert neuron_layers["route_count"] >= 6
    assert "test_neuron_layers_contract.py" in neuron_layers["direct_contract_test_files"]
    assert "test_neuron_layers_contract.py" in neuron_layers["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.neuron_layers" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.neuron_layers"


def test_runtime_contract_inventory_marks_performance_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    performance = route_heavy["copilot_core.api.v1.performance"]
    assert performance["route_count"] >= 6
    assert "test_performance_contract.py" in performance["direct_contract_test_files"]
    assert "test_performance_contract.py" in performance["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.performance" not in top_modules
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.performance"


def test_runtime_contract_inventory_marks_search_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.search")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.search",
    )

    assert source is not None
    assert module.count_routes(source) >= 4
    assert "test_search_contract.py" in direct_contract_test_files
    assert "test_search_contract.py" in direct_test_files
    assert data["recommended_next_slice"] is None or data["recommended_next_slice"]["module_path"] != "copilot_core.api.v1.search"


def test_runtime_contract_inventory_marks_debug_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.debug")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.debug",
    )

    assert source is not None
    assert module.count_routes(source) >= 2
    assert "test_debug_contract.py" in direct_contract_test_files
    assert "test_debug_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_learning_viz_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    learning_viz = route_heavy["copilot_core.api.v1.learning_viz"]
    assert learning_viz["route_count"] >= 5
    assert "test_learning_viz_contract.py" in learning_viz["direct_contract_test_files"]
    assert "test_learning_viz_contract.py" in learning_viz["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.learning_viz" not in top_modules
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_suggestions_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)
    route_heavy = {
        row["module_path"]: row
        for row in data["route_heavy_surfaces"]
    }

    suggestions = route_heavy["copilot_core.api.v1.suggestions"]
    assert suggestions["route_count"] >= 5
    assert "test_suggestions_contract.py" in suggestions["direct_contract_test_files"]
    assert "test_suggestions_contract.py" in suggestions["direct_test_files"]

    top_modules = [row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]]
    assert "copilot_core.api.v1.suggestions" not in top_modules
    assert data["summary"]["route_heavy_without_direct_contract_tests"] == 0
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_brain_growth_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE
    assert "test_brain_growth_contract.py" in module.collect_test_files(REPO_ROOT, "copilot_core.api.v1.brain_growth")[1]
    assert "copilot_core.api.v1.brain_growth" not in [
        row["module_path"] for row in data["top_uncovered_route_heavy_surfaces"]
    ]


def test_runtime_contract_inventory_marks_character_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.character")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.character",
    )

    assert source is not None
    assert module.count_routes(source) >= 4
    assert "test_character_contract.py" in direct_contract_test_files
    assert "test_character_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_action_attribution_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.action_attribution")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.action_attribution",
    )

    assert source is not None
    assert module.count_routes(source) >= 3
    assert "test_action_attribution_contract.py" in direct_contract_test_files
    assert "test_action_attribution_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_cache_control_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.cache_control")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.cache_control",
    )

    assert source is not None
    assert module.count_routes(source) >= 3
    assert "test_cache_control_contract.py" in direct_contract_test_files
    assert "test_cache_control_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_conflict_resolution_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.conflict_resolution")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.conflict_resolution",
    )

    assert source is not None
    assert module.count_routes(source) >= 3
    assert "test_conflict_resolution_contract.py" in direct_contract_test_files
    assert "test_conflict_resolution_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_error_digest_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.error_digest")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.error_digest",
    )

    assert source is not None
    assert module.count_routes(source) >= 3
    assert "test_error_digest_contract.py" in direct_contract_test_files
    assert "test_error_digest_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_events_ingest_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.events_ingest")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.events_ingest",
    )

    assert source is not None
    assert module.count_routes(source) >= 3
    assert "test_events_ingest_contract.py" in direct_contract_test_files
    assert "test_events_ingest_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_haushalt_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.haushalt")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.haushalt",
    )

    assert source is not None
    assert module.count_routes(source) >= 3
    assert "test_haushalt_contract.py" in direct_contract_test_files
    assert "test_haushalt_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_marks_module_health_as_directly_contract_covered() -> None:
    data = module.build_inventory(REPO_ROOT)

    source = module.resolve_module_source(REPO_ROOT, "copilot_core.api.v1.module_health")
    direct_test_files, direct_contract_test_files = module.collect_test_files(
        REPO_ROOT,
        "copilot_core.api.v1.module_health",
    )

    assert source is not None
    assert module.count_routes(source) >= 3
    assert "test_module_health_contract.py" in direct_contract_test_files
    assert "test_module_health_contract.py" in direct_test_files
    assert data["recommended_next_slice"] == CURRENT_RECOMMENDED_NEXT_SLICE


def test_runtime_contract_inventory_markdown_renders_dynamic_recommendation() -> None:
    markdown = module.render_markdown(
        {
            "summary": {
                "core_blueprint_entries": 1,
                "route_heavy_surfaces": 1,
                "route_heavy_without_direct_contract_tests": 1,
            },
            "recommended_next_slice": {
                "module_path": "copilot_core.api.v1.media_zones",
                "source_path": "copilot_core/rootfs/usr/src/app/copilot_core/api/v1/media_zones.py",
                "route_count": 23,
                "direct_test_files": [],
                "direct_contract_test_files": [],
            },
            "top_uncovered_route_heavy_surfaces": [],
        }
    )

    assert "Direkte Contract-Baseline für copilot_core.api.v1.media_zones" in markdown
    assert "`copilot_core.api.v1.media_zones` der schärfste nächste Kandidat" in markdown
    assert "route-starke, bislang nicht direkt kontraktabgedeckte Runtime-Surface" in markdown
    assert "Zone Editor Runtime Contract Baseline" not in markdown


def test_runtime_contract_inventory_markdown_handles_below_route_heavy_recommendation() -> None:
    markdown = module.render_markdown(
        {
            "summary": {
                "core_blueprint_entries": 99,
                "route_heavy_surfaces": 48,
                "route_heavy_without_direct_contract_tests": 0,
            },
            "recommended_next_slice": {
                "module_path": "copilot_core.api.v1.events_ingest",
                "source_path": "copilot_core/rootfs/usr/src/app/copilot_core/api/v1/events_ingest.py",
                "route_count": 3,
                "direct_test_files": [],
                "direct_contract_test_files": [],
            },
            "top_uncovered_route_heavy_surfaces": [],
        }
    )

    assert "direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle" in markdown
    assert "nächste direkt ungetestete Runtime-Surface unterhalb der Route-Heavy-Schwelle" in markdown
    assert "`copilot_core.api.v1.events_ingest` der schärfste nächste Kandidat" in markdown
