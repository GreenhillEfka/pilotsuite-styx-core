from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reload_repo_root_package():
    for name in list(sys.modules):
        if name == "copilot_core" or name.startswith("copilot_core."):
            sys.modules.pop(name, None)
    return importlib.import_module("copilot_core")


def test_repo_root_runtime_version_forwards_to_addon_versioning():
    copilot_core = _reload_repo_root_package()
    from copilot_core.versioning import get_runtime_version

    assert copilot_core.__version__ == get_runtime_version()
    assert copilot_core.__version__ != "0.0.0"


def test_repo_root_public_api_symbols_match___all__():
    copilot_core = _reload_repo_root_package()

    missing = [name for name in copilot_core.__all__ if not hasattr(copilot_core, name)]
    assert missing == []


def test_repo_root_requires_homeassistant_runtime_for_integration_entrypoints():
    copilot_core = _reload_repo_root_package()

    with pytest.raises(ModuleNotFoundError, match="homeassistant is required"):
        copilot_core._require_homeassistant_runtime()
