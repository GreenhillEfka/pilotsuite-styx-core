#!/usr/bin/env python3
"""Analyze blueprint config vs actual importability/attributes for H2.

Generates a machine-readable drift list and a human-readable reconciliation
report. Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def load_blueprint_config(repo_root: Path) -> tuple[list[tuple[str, str, str | None]], list[tuple[str, str, str | None]]]:
    path = repo_root / "copilot_core" / "blueprints_config.py"
    spec = importlib.util.spec_from_file_location("h2_blueprints_config", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load blueprint config: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.CORE_API_BLUEPRINTS), list(module.EXTERNAL_BLUEPRINTS)


def ensure_paths(repo_root: Path) -> None:
    for path in (
        repo_root,
        repo_root / "copilot_core" / "rootfs" / "usr" / "src" / "app",
    ):
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


def analyze_entries(entries: list[tuple[str, str, str | None]], lane: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for module_path, attr_name, url_prefix in entries:
        row: dict[str, Any] = {
            "lane": lane,
            "module_path": module_path,
            "attr_name": attr_name,
            "url_prefix": url_prefix,
            "import_ok": False,
            "attr_ok": False,
            "status": "unknown",
            "error_type": None,
            "error": None,
        }
        try:
            module = importlib.import_module(module_path)
            row["import_ok"] = True
            if hasattr(module, attr_name):
                row["attr_ok"] = True
                row["status"] = "ok"
            else:
                row["status"] = "attribute_missing"
                row["error_type"] = "AttributeError"
                row["error"] = f"{module_path} has no attribute {attr_name}"
        except Exception as exc:
            row["status"] = "import_failed"
            row["error_type"] = type(exc).__name__
            row["error"] = str(exc)
        results.append(row)
    return results


def priority_for(row: dict[str, Any]) -> int:
    if row["status"] == "ok":
        return 99
    err = row.get("error_type")
    if err in {"SyntaxError", "NameError"}:
        return 1
    if err in {"ImportError", "ModuleNotFoundError"}:
        return 2
    if err == "AttributeError":
        return 3
    return 4


def build_report(repo_root: Path) -> dict[str, Any]:
    ensure_paths(repo_root)
    core_entries, external_entries = load_blueprint_config(repo_root)
    rows = analyze_entries(core_entries, "core") + analyze_entries(external_entries, "external")
    ok = [row for row in rows if row["status"] == "ok"]
    drifts = [row for row in rows if row["status"] != "ok"]
    drifts.sort(key=lambda row: (priority_for(row), row["module_path"]))

    by_error_type = Counter(row["error_type"] or "unknown" for row in drifts)
    by_status = Counter(row["status"] for row in rows)

    return {
        "repo_root": str(repo_root),
        "summary": {
            "total_entries": len(rows),
            "ok_entries": len(ok),
            "drift_entries": len(drifts),
            "status_breakdown": dict(by_status),
            "error_type_breakdown": dict(by_error_type),
        },
        "drifts": drifts,
        "top_priorities": drifts[:25],
        "recommended_fix_order": [
            "1. Fix SyntaxError/NameError modules first because they break registration deterministically.",
            "2. Fix ModuleNotFoundError/ImportError next by restoring bridge paths or correcting module references.",
            "3. Fix AttributeError mismatches by aligning blueprint attr names in blueprints_config to real exports.",
            "4. Re-run core wiring tests after each batch, then regenerate this report.",
        ],
        "check_commands": [
            "python3 -m py_compile copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py",
            "python3 -m pytest -q tests/test_h1_truth_map.py tests/test_api_v1_syntax_contract.py tests/test_core_wiring_contract.py",
            "python3 scripts/h2_blueprint_reconcile.py --repo . --md-out docs/analysis/H2_BLUEPRINT_RECONCILIATION.md --json-out docs/analysis/h2_blueprint_reconciliation.json",
        ],
    }


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# H2 Blueprint / OpenAPI / Runtime Reconciliation",
        "",
        "## Summary",
        f"- Total config entries checked: **{summary['total_entries']}**",
        f"- Import/attr OK: **{summary['ok_entries']}**",
        f"- Drift entries: **{summary['drift_entries']}**",
        f"- Status breakdown: `{summary['status_breakdown']}`",
        f"- Error breakdown: `{summary['error_type_breakdown']}`",
        "",
        "## Top Priority Drift Cases",
    ]
    for row in data["top_priorities"][:20]:
        lines.append(
            f"- **{row['error_type']}** `{row['module_path']}` :: expected `{row['attr_name']}`"
            + (f" — {row['error']}" if row['error'] else "")
        )

    lines += ["", "## Recommended Fix Order"]
    for item in data["recommended_fix_order"]:
        lines.append(f"- {item}")

    lines += ["", "## Check Commands"]
    for cmd in data["check_commands"]:
        lines.append(f"- `{cmd}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="/config/clawd/team/worktrees/pilotsuite-styx-core-current")
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    parser.add_argument("--stdout-json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    data = build_report(repo_root)

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.md_out:
        path = Path(args.md_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(data) + "\n", encoding="utf-8")

    if args.stdout_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
