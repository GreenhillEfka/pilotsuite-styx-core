"""Contract tests for optional UI blueprint loading in core_setup."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


import copilot_core.core_setup as core_setup  # noqa: E402


OPTIONAL_UI_MODULES = {
    "copilot_core.api.v1.backend_ui",
    "copilot_core.api.v1.neurons_ui",
    "copilot_core.api.v1.rag_ui",
    "copilot_core.api.v1.chat",
    "copilot_core.api.v1.learning_viz",
    "copilot_core.api.v1.media_ui",
}


def test_register_blueprints_tolerates_missing_optional_ui_modules(monkeypatch):
    real_import_module = core_setup.importlib.import_module

    def fake_import_module(module_path: str):
        if module_path in OPTIONAL_UI_MODULES:
            raise ImportError(f"simulated missing module: {module_path}")
        return real_import_module(module_path)

    monkeypatch.setattr(core_setup.importlib, "import_module", fake_import_module)

    app = Flask(__name__)
    core_setup.register_blueprints(app, {})

    rules = {str(rule) for rule in app.url_map.iter_rules()}
    assert "/api/v1/anomaly/model/status" in rules
    assert "/api/v1/calendar" in rules
