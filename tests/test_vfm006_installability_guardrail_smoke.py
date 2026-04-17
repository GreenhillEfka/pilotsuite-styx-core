from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = REPO_ROOT / "addons" / "pilotsuite" / "app"
ADDON_PACKAGE = ADDON_APP / "copilot_core"
ROOT_VERSION_FILE = REPO_ROOT / "VERSION"
ADDON_VERSION_FILE = ADDON_APP / "VERSION"
ADDON_CONFIG = REPO_ROOT / "addons" / "pilotsuite" / "config.yaml"
SYNC_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sync-versions.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
LOCAL_HA_METADATA_SURFACES = [
    REPO_ROOT / "custom_components" / "pilotsuite" / "manifest.json",
    REPO_ROOT / "custom_components" / "pilotsuite" / "hacs.json",
    REPO_ROOT / "custom_components" / "pilotsuite" / "config_flow.py",
]
LEGACY_TOP_LEVEL_HA_SURFACES = [
    REPO_ROOT / "copilot_core" / "manifest.json",
    REPO_ROOT / "copilot_core" / "hacs.json",
    REPO_ROOT / "copilot_core" / "config_flow.py",
]
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def _config_version() -> str:
    text = ADDON_CONFIG.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version:\s*"([^"]+)"\s*$', text)
    assert match, "addons/pilotsuite/config.yaml must expose a quoted version field"
    return match.group(1)


def test_addon_version_surfaces_stay_canonical_for_core_installation() -> None:
    root_version = ROOT_VERSION_FILE.read_text(encoding="utf-8").strip()
    addon_version = ADDON_VERSION_FILE.read_text(encoding="utf-8").strip()
    config_version = _config_version()

    assert root_version == addon_version == config_version
    assert SEMVER_RE.fullmatch(root_version)
    assert (REPO_ROOT / "addons" / "pilotsuite" / "Dockerfile").exists()


def test_ha_manifest_ownership_stays_externalized_to_the_ha_repo() -> None:
    sync_text = SYNC_WORKFLOW.read_text(encoding="utf-8")
    release_text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "repository: ${{ github.repository_owner }}/pilotsuite-styx-ha" in sync_text
    assert "../ha-repo/custom_components/pilotsuite/manifest.json" in sync_text
    assert "custom_components/pilotsuite/manifest.json" in sync_text
    assert "addons/pilotsuite/app/VERSION" in sync_text
    assert "addons/pilotsuite/config.yaml" in sync_text
    assert "copilot_core/manifest.json" not in sync_text
    assert "copilot_core/hacs.json" not in sync_text
    assert "copilot_core/config_flow.py" not in sync_text

    assert "addons/pilotsuite/app/VERSION" in release_text
    assert "addons/pilotsuite/config.yaml" in release_text
    assert "copilot_core/(config_flow\\.py|manifest\\.json|hacs\\.json|README\\.md|ui/)" in release_text

    for path in LOCAL_HA_METADATA_SURFACES + LEGACY_TOP_LEVEL_HA_SURFACES:
        assert not path.exists(), f"unexpected local HA-owned surface present: {path.relative_to(REPO_ROOT)}"


def test_addon_import_path_resolves_from_addon_app_without_legacy_ha_surfaces(monkeypatch) -> None:
    monkeypatch.delenv("COPILOT_VERSION", raising=False)
    monkeypatch.delenv("BUILD_VERSION", raising=False)

    for name in list(sys.modules):
        if name == "copilot_core" or name.startswith("copilot_core."):
            sys.modules.pop(name, None)

    monkeypatch.syspath_prepend(str(ADDON_APP))

    package = importlib.import_module("copilot_core")
    versioning = importlib.import_module("copilot_core.versioning")
    api_version = importlib.import_module("copilot_core.api.api_version")

    assert Path(package.__file__).resolve() == (ADDON_PACKAGE / "__init__.py").resolve()
    assert versioning.get_runtime_version() == ADDON_VERSION_FILE.read_text(encoding="utf-8").strip()
    assert api_version.API_VERSION == "1.0"

    for path in LEGACY_TOP_LEVEL_HA_SURFACES:
        assert not path.exists(), f"legacy surface unexpectedly restored: {path.relative_to(REPO_ROOT)}"
