"""Contract coverage for flat blueprint registry attributes/importability."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
CORE_SETUP_PATH = APP_ROOT / "copilot_core" / "core_setup.py"

path_str = str(APP_ROOT)
if APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


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


def test_flat_blueprint_registry_modules_import_and_expose_declared_attributes() -> None:
    failures: list[str] = []

    for module_path, blueprint_attr, _prefix in _blueprint_entries():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:  # pragma: no cover - exercised only on failure
            failures.append(f"{module_path}: import failed: {type(exc).__name__}: {exc}")
            continue

        if not hasattr(module, blueprint_attr):
            failures.append(f"{module_path}: missing blueprint attr {blueprint_attr}")

    assert not failures, "\n".join(failures)
