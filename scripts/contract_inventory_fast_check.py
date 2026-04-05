#!/usr/bin/env python3
"""Fast contract inventory guard for PilotSuite Core.

Purpose:
- run a cheap per-commit / per-write-cycle contract sanity check
- avoid waiting for slice boundaries to catch obvious runtime/contract regressions
- complement (not replace) the full OpenAPI/runtime drift check

Checks:
1. all CORE_API_BLUEPRINTS module paths resolve to source files
2. runtime contract inventory builds successfully
3. route-heavy surfaces do not regress into missing direct contract coverage

Usage:
    python3 scripts/contract_inventory_fast_check.py --repo .

Exit codes:
    0 — fast check passed
    1 — contract regression detected
    2 — script/config error
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast contract inventory guard for PilotSuite Core")
    parser.add_argument("--repo", type=str, default=".", help="Repository root")
    return parser.parse_args()


def load_inventory_module(repo_root: Path):
    script_path = repo_root / "scripts" / "ps_core_runtime_contract_inventory.py"
    spec = importlib.util.spec_from_file_location("ps_core_runtime_contract_inventory_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load inventory script from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo).resolve()

    try:
        inventory = load_inventory_module(repo_root)
        rows = inventory.load_blueprint_entries(repo_root)
        missing_sources: list[str] = []
        for module_path, _attr_name, _url_prefix in rows:
            if inventory.resolve_module_source(repo_root, module_path) is None:
                missing_sources.append(module_path)

        data = inventory.build_inventory(repo_root)
        route_heavy_uncovered = data["summary"]["route_heavy_without_direct_contract_tests"]
    except Exception as exc:
        print(f"ERROR: fast contract inventory check failed to execute: {exc}")
        return 2

    failed = False
    print("Fast Contract Inventory Check")
    print("=" * 40)
    print(f"Repo: {repo_root}")
    print(f"Blueprint entries: {len(rows)}")
    print(f"Route-heavy uncovered: {route_heavy_uncovered}")

    if missing_sources:
        failed = True
        print()
        print(f"❌ Missing runtime sources ({len(missing_sources)}):")
        for module_path in missing_sources[:20]:
            print(f"  - {module_path}")
        if len(missing_sources) > 20:
            print(f"  ... and {len(missing_sources) - 20} more")

    if route_heavy_uncovered > 0:
        failed = True
        print()
        print("❌ Route-heavy surfaces without direct contract coverage:")
        for row in data.get("top_uncovered_route_heavy_surfaces", [])[:12]:
            print(
                f"  - {row['module_path']} (routes={row['route_count']}, "
                f"contract_tests={len(row['direct_contract_test_files'])})"
            )

    recommended = data.get("recommended_next_slice")
    if recommended:
        print()
        print(
            "Next uncovered slice (informational): "
            f"{recommended['module_path']} (routes={recommended['route_count']})"
        )

    if failed:
        print()
        print("FAIL: fast contract inventory regression detected")
        return 1

    print()
    print("PASS: fast contract inventory check clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
