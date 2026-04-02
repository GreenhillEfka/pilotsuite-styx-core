from __future__ import annotations

import importlib
from pathlib import Path
import sys

from flask import Blueprint


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from copilot_core.blueprints_config import get_all_blueprints, validate_blueprint_config  # noqa: E402


def test_blueprints_config_is_globally_valid() -> None:
    ok, errors = validate_blueprint_config()
    assert ok is True
    assert errors == []


def test_all_configured_blueprints_import_as_flask_blueprints() -> None:
    for module_path, blueprint_name, _prefix in get_all_blueprints():
        module = importlib.import_module(module_path)
        blueprint = getattr(module, blueprint_name)
        assert isinstance(blueprint, Blueprint), f"{module_path}.{blueprint_name} is not a Flask Blueprint"
