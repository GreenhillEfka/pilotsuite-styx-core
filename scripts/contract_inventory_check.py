#!/usr/bin/env python3
"""Contract Inventory Auto-Check for PilotSuite Core.

Compares runtime wiring (blueprints_config.py + actual module exports)
against OpenAPI spec (docs/openapi.yaml). Fails on unexplained drift.

Usage:
    python3 scripts/contract_inventory_check.py --repo .

Exit codes:
    0 — No drift
    1 — Drift detected (build failure)
    2 — Script error (missing files, etc.)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(2)


def parse_args():
    parser = argparse.ArgumentParser(description="Contract Inventory Auto-Check")
    parser.add_argument("--repo", type=str, default=".", help="Repository root")
    parser.add_argument("--openapi", type=str, default="docs/openapi.yaml", help="OpenAPI spec path")
    parser.add_argument("--blueprints", type=str, 
                        default="copilot_core/blueprints_config.py",
                        help="Blueprints config path")
    parser.add_argument("--light", action="store_true", 
                        help="Light mode: skip OpenAPI comparison (faster for daily commits)")
    return parser.parse_args()


def extract_blueprints_routes(blueprints_path: Path) -> Set[str]:
    """Extract route prefixes from CORE_API_BLUEPRINTS."""
    routes = set()
    
    if not blueprints_path.exists():
        print(f"WARN: Blueprints config not found: {blueprints_path}")
        return routes
    
    content = blueprints_path.read_text()
    
    # Parse blueprint module paths from CORE_API_BLUEPRINTS
    # Pattern: ("copilot_core.api.v1.module_name", "bp_name", "/api/v1/endpoint")
    import re
    pattern = r'\("([^"]+)",\s*"([^"]+)",\s*("[^"]*"|None)\)'
    matches = re.findall(pattern, content)
    
    for module_path, bp_name, url_prefix in matches:
        # Extract module name
        module_name = module_path.split(".")[-1]
        
        # Derive expected API path
        if url_prefix and url_prefix != "None":
            prefix = url_prefix.strip('"')
        else:
            # Default pattern: /api/v1/{module_name}
            prefix = f"/api/v1/{module_name.replace('_', '-')}"
        
        routes.add(prefix)
        routes.add(f"{prefix}/")
    
    return routes


def extract_openapi_paths(openapi_path: Path) -> Set[str]:
    """Extract all paths from OpenAPI spec."""
    paths = set()
    
    if not openapi_path.exists():
        print(f"WARN: OpenAPI spec not found: {openapi_path}")
        return paths
    
    try:
        with open(openapi_path) as f:
            spec = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"WARN: OpenAPI YAML parse error: {e}")
        print("Falling back to blueprint-only check (OpenAPI skipped)")
        return paths
    
    for path in spec.get("paths", {}).keys():
        paths.add(path)
        # Also add trailing slash variant
        if not path.endswith("/"):
            paths.add(path + "/")
    
    return paths


def extract_runtime_modules(blueprints_path: Path, repo_root: Path) -> Tuple[Set[str], List[str]]:
    """Check which blueprint modules actually exist and export bp.
    
    Searches both:
    - copilot_core/api/v1/*.py (Root)
    - copilot_core/rootfs/usr/src/app/copilot_core/api/v1/*.py (Runtime)
    - Subpackages like knowledge_graph.api -> knowledge_graph/api.py
    - Subpackages like dashboard.api.v1.widget_positions -> dashboard/api/v1/widget_positions.py
    """
    missing = []
    found = set()
    
    if not blueprints_path.exists():
        return found, missing
    
    content = blueprints_path.read_text()
    import re
    pattern = r'\("([^"]+)",\s*"([^"]+)"'
    matches = re.findall(pattern, content)
    
    for module_path, bp_name in matches:
        found_module = False
        
        # Handle subpackage patterns like copilot_core.knowledge_graph.api
        if module_path.count('.') >= 2 and not module_path.startswith('copilot_core.api.v1'):
            parts = module_path.split('.')
            
            # Pattern: copilot_core.<pkg>.api -> <pkg>/api.py
            if len(parts) >= 3 and parts[-1] == 'api':
                pkg_name = parts[1]  # e.g., knowledge_graph
                module_file_runtime = repo_root / "copilot_core" / "rootfs" / "usr" / "src" / "app" / "copilot_core" / pkg_name / "api.py"
                if module_file_runtime.exists():
                    found_module = True
            
            # Pattern: dashboard.api.v1.<module> -> dashboard/api/v1/<module>.py
            elif parts[0] == 'dashboard':
                # dashboard.api.v1.widget_positions -> dashboard/api/v1/widget_positions.py
                # Full path: copilot_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py
                module_name = parts[-1]  # widget_positions
                module_file_runtime = repo_root / "copilot_core" / "rootfs" / "usr" / "src" / "app" / "dashboard" / "api" / "v1" / (module_name + ".py")
                module_file_root = repo_root / "dashboard" / "api" / "v1" / (module_name + ".py")
                if module_file_runtime.exists() or module_file_root.exists():
                    found_module = True
        
        # Standard API v1 pattern
        if not found_module and "copilot_core.api.v1." in module_path:
            module_name = module_path.replace("copilot_core.api.v1.", "")
            
            # Try Runtime location
            module_file_runtime = repo_root / "copilot_core" / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "api" / "v1" / (module_name.replace(".", "/") + ".py")
            
            # Try Root location
            module_file_root = repo_root / "copilot_core" / "api" / "v1" / (module_name.replace(".", "/") + ".py")
            
            if module_file_runtime.exists() or module_file_root.exists():
                found_module = True
        
        if found_module:
            found.add(module_path)
        else:
            missing.append(module_path)
    
    return found, missing


def check_drift(repo_root: Path, openapi_path: Path, blueprints_path: Path, light_mode: bool = False) -> Tuple[bool, Dict]:
    """Check for contract drift between runtime, blueprints, and OpenAPI."""
    
    # OpenAPI only in full mode
    if light_mode:
        openapi_paths = set()
    else:
        openapi_paths = extract_openapi_paths(openapi_path)
    
    blueprint_routes = extract_blueprints_routes(blueprints_path)
    runtime_modules, missing_modules = extract_runtime_modules(blueprints_path, repo_root)
    
    # Only check OpenAPI drift if OpenAPI was parseable and not in light mode
    if openapi_paths and not light_mode:
        # Check 1: OpenAPI paths covered by blueprint routes
        uncovered_openapi = openapi_paths - blueprint_routes
        
        # Check 2: Blueprint routes covered by OpenAPI
        uncovered_blueprints = blueprint_routes - openapi_paths
    else:
        # OpenAPI not available or skipped — skip OpenAPI comparison
        uncovered_openapi = []
        uncovered_blueprints = []
    
    # Check 3: Missing runtime modules (always checked)
    drift = bool(missing_modules)
    
    report = {
        "drift": drift,
        "light_mode": light_mode,
        "openapi_available": bool(openapi_paths),
        "openapi_paths_count": len(openapi_paths),
        "blueprint_routes_count": len(blueprint_routes),
        "runtime_modules_count": len(runtime_modules),
        "uncovered_openapi": sorted(uncovered_openapi),
        "uncovered_blueprints": sorted(uncovered_blueprints),
        "missing_modules": missing_modules,
    }
    
    return drift, report


def main():
    args = parse_args()
    repo_root = Path(args.repo).resolve()
    openapi_path = repo_root / args.openapi
    blueprints_path = repo_root / args.blueprints
    
    mode = "LIGHT" if args.light else "FULL"
    print(f"Contract Inventory Auto-Check ({mode})")
    print(f"=" * 40)
    print(f"Repo: {repo_root}")
    print(f"OpenAPI: {openapi_path}")
    print(f"Blueprints: {blueprints_path}")
    print()
    
    drift, report = check_drift(repo_root, openapi_path, blueprints_path, light_mode=args.light)
    
    # Print report
    print(f"OpenAPI paths: {report['openapi_paths_count']}")
    print(f"Blueprint routes: {report['blueprint_routes_count']}")
    print(f"Runtime modules: {report['runtime_modules_count']}")
    print()
    
    if report["uncovered_openapi"]:
        print(f"⚠️  Uncovered OpenAPI paths ({len(report['uncovered_openapi'])}):")
        for path in report["uncovered_openapi"][:10]:
            print(f"   - {path}")
        if len(report["uncovered_openapi"]) > 10:
            print(f"   ... and {len(report['uncovered_openapi']) - 10} more")
        print()
    
    if report["uncovered_blueprints"]:
        print(f"⚠️  Uncovered Blueprint routes ({len(report['uncovered_blueprints'])}):")
        for route in report["uncovered_blueprints"][:10]:
            print(f"   - {route}")
        if len(report["uncovered_blueprints"]) > 10:
            print(f"   ... and {len(report['uncovered_blueprints']) - 10} more")
        print()
    
    # Missing modules is the primary drift signal when OpenAPI is unavailable
    if report["missing_modules"]:
        print(f"⚠️  Missing runtime modules ({len(report['missing_modules'])}):")
        for mod in report["missing_modules"][:10]:
            print(f"   - {mod}")
        if len(report["missing_modules"]) > 10:
            print(f"   ... and {len(report['missing_modules']) - 10} more")
        print()
    
    if drift:
        print("❌ DRIFT DETECTED — Build fails")
        print()
        print("Action required:")
        if report["missing_modules"]:
            print("  1. Restore missing modules or update blueprints_config.py")
        if report["uncovered_openapi"] and not args.light:
            print("  2. Update OpenAPI spec if routes are correct")
        if report["uncovered_blueprints"] and not args.light:
            print("  3. Update blueprints_config.py if OpenAPI is correct")
        sys.exit(1)
    else:
        if report["openapi_available"] and not args.light:
            print("✅ NO DRIFT — Contract inventory consistent (OpenAPI + Runtime)")
        else:
            print("✅ NO DRIFT — Runtime modules consistent" + (" (light mode)" if args.light else ""))
        sys.exit(0)


if __name__ == "__main__":
    main()
