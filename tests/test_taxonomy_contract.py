"""Regression coverage for the taxonomy authority."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.core.taxonomy import classify_entity  # noqa: E402


def test_balcony_entities_resolve_to_terrace_zone_hint() -> None:
    classification = classify_entity("light.balkon_licht", "on")

    assert classification.zone_type_hint == "terrace"
    assert classification.module_bucket == "licht"
    assert "indoor" in classification.tags or "outdoor" in classification.tags


def test_loggia_entities_resolve_to_terrace_zone_hint() -> None:
    classification = classify_entity("sensor.loggia_temperature", "19.5")

    assert classification.zone_type_hint == "terrace"
    assert classification.role.value == "climate"


def test_garden_entities_still_resolve_to_outside_zone_hint() -> None:
    classification = classify_entity("binary_sensor.garden_motion", "on")

    assert classification.zone_type_hint == "outside"
    assert classification.role.value == "motion"
    assert classification.module_bucket == "bewegung"
