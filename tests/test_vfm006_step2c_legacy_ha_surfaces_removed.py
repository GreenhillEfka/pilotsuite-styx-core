from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_HA_SURFACES = [
    "copilot_core/config_flow.py",
    "copilot_core/manifest.json",
    "copilot_core/hacs.json",
    "copilot_core/README.md",
    "copilot_core/ui/accessibility.py",
    "copilot_core/ui/admin_dashboard.py",
    "copilot_core/ui/analytics_dashboard.py",
    "copilot_core/ui/lovelace_cards.py",
    "copilot_core/ui/mobile_optimization.py",
    "copilot_core/ui/onboarding.py",
    "copilot_core/ui/theme_manager.py",
    "copilot_core/ui/README.md",
]


def test_legacy_ha_repo_side_surfaces_are_removed() -> None:
    missing = [path for path in LEGACY_HA_SURFACES if not (REPO_ROOT / path).exists()]
    assert missing == LEGACY_HA_SURFACES
