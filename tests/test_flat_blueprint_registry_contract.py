"""Contract coverage for flat blueprint registry module paths."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
CORE_SETUP_PATH = APP_ROOT / "copilot_core" / "core_setup.py"


def _blueprint_entries() -> list[tuple[str, str, object]]:
    module = ast.parse(CORE_SETUP_PATH.read_text(encoding="utf-8"))
    entries: list[tuple[str, str, object]] = []

    for node in ast.walk(module):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "_BLUEPRINTS" for target in node.targets):
            continue
        if not isinstance(node.value, ast.List):
            continue

        for elt in node.value.elts:
            if not isinstance(elt, ast.Tuple) or len(elt.elts) < 2:
                continue
            values: list[object] = []
            for part in elt.elts[:3]:
                values.append(part.value if isinstance(part, ast.Constant) else None)
            module_path, blueprint_attr, prefix = values
            if isinstance(module_path, str) and isinstance(blueprint_attr, str):
                entries.append((module_path, blueprint_attr, prefix))

    return entries


def test_flat_blueprint_registry_points_only_to_existing_modules() -> None:
    missing: list[str] = []

    for module_path, _bp_attr, _prefix in _blueprint_entries():
        rel = Path(*module_path.split("."))
        py_path = APP_ROOT / f"{rel}.py"
        pkg_init = APP_ROOT / rel / "__init__.py"
        if not py_path.exists() and not pkg_init.exists():
            missing.append(module_path)

    assert not missing, "Missing blueprint modules: " + ", ".join(sorted(missing))
