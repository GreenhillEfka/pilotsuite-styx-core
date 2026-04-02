from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "h2_blueprint_reconcile.py"

spec = importlib.util.spec_from_file_location("h2_blueprint_reconcile", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_h2_blueprint_reconcile_detects_remaining_drift() -> None:
    data = module.build_report(REPO_ROOT)

    assert data["summary"]["total_entries"] >= 90
    assert data["summary"]["drift_entries"] > 0
    assert len(data["top_priorities"]) > 0


def test_h2_blueprint_reconcile_includes_fix_commands() -> None:
    data = module.build_report(REPO_ROOT)

    assert any("py_compile" in cmd for cmd in data["check_commands"])
    assert any("pytest" in cmd for cmd in data["check_commands"])
