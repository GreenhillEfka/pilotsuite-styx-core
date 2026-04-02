from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "h1_truth_map.py"


spec = importlib.util.spec_from_file_location("h1_truth_map", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_h1_truth_map_detects_runtime_as_primary_surface() -> None:
    data = module.build_truth_map(REPO_ROOT)

    assert data["counts"]["runtime_api_python_files"] > data["counts"]["repo_api_python_files"]
    assert data["counts"]["blueprints_config_core_entries"] >= 80
    assert data["counts"]["docs_openapi_paths"] >= 100


def test_h1_truth_map_flags_legacy_docs() -> None:
    data = module.build_truth_map(REPO_ROOT)

    assert data["doc_truth_markers"]["api_reference"]["legacy"] is True
    assert data["doc_truth_markers"]["api_complete"]["legacy"] is True


def test_h1_truth_map_reports_runtime_wiring_validity_state() -> None:
    data = module.build_truth_map(REPO_ROOT)

    compile_state = data["runtime_validity"]["core_setup_py_compile"]
    assert isinstance(compile_state["ok"], bool)
    if compile_state["ok"]:
        assert not any(blocker["area"] == "runtime_wiring" for blocker in data["blockers"])
    else:
        assert any(
            blocker["area"] == "runtime_wiring" and blocker["severity"] == "critical"
            for blocker in data["blockers"]
        )
