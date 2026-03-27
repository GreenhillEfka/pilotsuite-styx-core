"""Regression coverage for the brain growth read model."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


import copilot_core.core.brain_read_model as brain_read_model  # noqa: E402


def _fresh_module():
    return importlib.reload(brain_read_model)


def test_cached_graph_snapshot_survives_missing_service() -> None:
    mod = _fresh_module()

    mod.update_graph_growth_snapshot(
        total_nodes=12,
        total_edges=18,
        nodes_by_kind={"zone": 4, "entity": 8},
        edges_by_type={"observed_in": 10, "belongs_to": 8},
        top_active_nodes=[{"id": "entity.light.living_room", "score": 0.99}],
    )

    snapshot = mod.build_brain_activity_snapshot(brain_graph_service=None)
    payload = snapshot.to_dict()

    assert payload["graph"]["total_nodes"] == 12
    assert payload["graph"]["total_edges"] == 18
    assert payload["graph"]["new_nodes_since_last"] == 12
    assert payload["graph"]["new_edges_since_last"] == 18
    assert payload["graph"]["nodes_by_kind"] == {"zone": 4, "entity": 8}
    assert payload["graph"]["edges_by_type"] == {"observed_in": 10, "belongs_to": 8}
    assert payload["graph"]["top_active_nodes"] == [{"id": "entity.light.living_room", "score": 0.99}]
    assert payload["graph"]["graph_version"] == 1


def test_recent_events_are_newest_first_and_include_state_projection() -> None:
    mod = _fresh_module()

    mod.feed_brain({"entity_id": "light.kitchen", "domain": "light", "kind": "state_changed", "new_state": "on", "ts": 100})
    mod.feed_brain({"entity_id": "sensor.temp", "domain": "sensor", "kind": "measurement", "new": {"state": 21.5}, "ts": 200})

    payload = mod.get_brain_summary(recent_events_limit=2)

    assert [event["entity_id"] for event in payload["recent_events"]] == ["sensor.temp", "light.kitchen"]
    assert payload["recent_events"][0]["state"] == "21.5"
    assert payload["recent_events"][1]["state"] == "on"


def test_module_context_uses_registry_defaults_when_registry_returns_empty() -> None:
    mod = _fresh_module()

    registry = SimpleNamespace(get_all_states=lambda: {})
    payload = mod.get_brain_summary(module_registry=registry)

    assert payload["module_context"]["licht"] == "active"
    assert payload["module_context"]["bewegung"] == "active"
    assert payload["module_context"]["mood_engine"] == "active"
