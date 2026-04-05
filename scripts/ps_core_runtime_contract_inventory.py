#!/usr/bin/env python3
"""Build a focused runtime/contract inventory for the active PilotSuite Core worktree.

Purpose:
- capture current runtime wiring truth from the active worktree
- map registry-backed API surfaces to their source files
- estimate direct contract-test coverage for route-heavy surfaces
- derive exactly one next repair slice from verifiable worktree evidence

The script intentionally uses only the Python standard library so it can run in
constrained environments.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


RECOMMENDATION_PRIORITY_BOOST: dict[str, int] = {
    "copilot_core.api.v1.zone_editor": 50,
    "copilot_core.api.v1.zone_dashboard": 35,
    "copilot_core.api.v1.zone_automation": 35,
    "copilot_core.api.v1.zone_automation_api": 30,
    "copilot_core.api.v1.module_control": 25,
    "copilot_core.api.v1.ha_module": 25,
    "copilot_core.api.v1.notifications": 20,
    "copilot_core.api.v1.reminders": 18,
    "copilot_core.api.v1.media_zones": 18,
    "copilot_core.api.v1.backend_ui": 15,
}

MODULE_TEST_ALIASES: dict[str, list[str]] = {
    "copilot_core.api.v1.action_closure": ["action_closure"],
    "copilot_core.api.v1.alarm": ["alarm"],
    "copilot_core.api.v1.anomaly": ["anomaly"],
    "copilot_core.api.v1.autonomy": ["autonomy"],
    "copilot_core.api.v1.backend_ui": ["backend_ui", "dashboard_tabs"],
    "copilot_core.api.v1.conversation": ["conversation"],
    "copilot_core.api.v1.energy_analytics": ["energy_analytics"],
    "copilot_core.api.v1.energy_forecast": ["energy_forecast", "energy_optimization"],
    "copilot_core.api.v1.entity_adoption": ["entity_adoption"],
    "copilot_core.api.v1.ha_module": ["ha_module", "ha_connection"],
    "copilot_core.api.v1.habitus": ["habitus"],
    "copilot_core.api.v1.homekit": ["homekit"],
    "copilot_core.api.v1.media_ui": ["media_ui"],
    "copilot_core.api.v1.media_zones": ["media_zones"],
    "copilot_core.api.v1.metrics": ["metrics"],
    "copilot_core.api.v1.ml_forecast": ["ml_forecast", "predictive"],
    "copilot_core.api.v1.module_control": ["module_control"],
    "copilot_core.api.v1.multizone": ["multizone"],
    "copilot_core.api.v1.notifications": ["notification", "notifications"],
    "copilot_core.api.v1.predictive": ["predictive"],
    "copilot_core.api.v1.proposals": ["proposal", "proposals", "proposal_lifecycle"],
    "copilot_core.api.v1.rag": ["rag"],
    "copilot_core.api.v1.rate_limit": ["rate_limit"],
    "copilot_core.api.v1.reminders": ["reminder", "reminders"],
    "copilot_core.api.v1.scenes": ["scenes"],
    "copilot_core.api.v1.shopping": ["shopping"],
    "copilot_core.api.v1.sonos": ["sonos"],
    "copilot_core.api.v1.suggestions": ["suggestion", "suggestions"],
    "copilot_core.api.v1.user_hints": ["user_hints"],
    "copilot_core.api.v1.users": ["users", "user_profile"],
    "copilot_core.api.v1.voice_context_bp": ["voice_context", "voice_"],
    "copilot_core.api.v1.zone_aggregates": ["zone_aggregates"],
    "copilot_core.api.v1.zone_automation": ["zone_automation"],
    "copilot_core.api.v1.zone_automation_api": ["zone_automation"],
    "copilot_core.api.v1.zone_dashboard": ["zone_dashboard"],
    "copilot_core.api.v1.zone_editor": ["zone_editor"],
    "copilot_core.api.v1.zone_health": ["zone_health"],
}


@dataclass
class SurfaceInventoryRow:
    module_path: str
    attr_name: str
    source_path: str | None
    route_count: int
    direct_test_files: list[str]
    direct_contract_test_files: list[str]
    priority_boost: int
    recommendation_score: int



def load_blueprint_entries(repo_root: Path) -> list[tuple[str, str, str | None]]:
    path = repo_root / "copilot_core" / "blueprints_config.py"
    spec = importlib.util.spec_from_file_location("ps_core_runtime_contract_inventory_blueprints", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load blueprint config from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.CORE_API_BLUEPRINTS)



def resolve_module_source(repo_root: Path, module_path: str) -> Path | None:
    relative = Path(*module_path.split("."))
    candidates = [
        repo_root / "copilot_core" / "rootfs" / "usr" / "src" / "app" / f"{relative}.py",
        repo_root / f"{relative}.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None



def count_routes(source_path: Path | None) -> int:
    if source_path is None:
        return 0
    tree = ast.parse(source_path.read_text(encoding="utf-8", errors="replace"))
    route_count = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "route":
                route_count += 1
    return route_count



def test_tokens_for(module_path: str) -> list[str]:
    explicit = MODULE_TEST_ALIASES.get(module_path)
    if explicit:
        return explicit

    base = module_path.split(".")[-1]
    tokens = [base]
    if base.endswith("_api"):
        tokens.append(base[:-4])
    return tokens



def collect_test_files(repo_root: Path, module_path: str) -> tuple[list[str], list[str]]:
    tests_dir = repo_root / "tests"
    filenames = sorted(path.name for path in tests_dir.glob("test_*.py"))
    tokens = test_tokens_for(module_path)
    direct = [name for name in filenames if any(token in name for token in tokens)]
    if module_path == "copilot_core.api.v1.rag":
        direct = [name for name in direct if "rag_ui" not in name]
    contract = [name for name in direct if "contract" in name or name.endswith("_api.py") or "blueprint" in name]
    return direct, contract



def build_inventory(repo_root: Path) -> dict[str, Any]:
    rows: list[SurfaceInventoryRow] = []
    for module_path, attr_name, _url_prefix in load_blueprint_entries(repo_root):
        source_path = resolve_module_source(repo_root, module_path)
        route_count = count_routes(source_path)
        direct_tests, direct_contract_tests = collect_test_files(repo_root, module_path)
        priority_boost = RECOMMENDATION_PRIORITY_BOOST.get(module_path, 0)

        recommendation_score = 0
        if route_count > 0 and not direct_contract_tests:
            recommendation_score = route_count * 10 + priority_boost
            if not direct_tests:
                recommendation_score += 20

        rows.append(
            SurfaceInventoryRow(
                module_path=module_path,
                attr_name=attr_name,
                source_path=str(source_path.relative_to(repo_root)) if source_path else None,
                route_count=route_count,
                direct_test_files=direct_tests,
                direct_contract_test_files=direct_contract_tests,
                priority_boost=priority_boost,
                recommendation_score=recommendation_score,
            )
        )

    rows.sort(key=lambda row: (-row.recommendation_score, -row.route_count, row.module_path))
    recommended = next((row for row in rows if row.recommendation_score > 0), None)
    route_heavy = [row for row in rows if row.route_count >= 5]
    uncovered_route_heavy = [row for row in route_heavy if not row.direct_contract_test_files]

    inventory = {
        "repo_root": str(repo_root),
        "generated_from": {
            "blueprints_config": "copilot_core/blueprints_config.py",
            "runtime_root": "copilot_core/rootfs/usr/src/app",
            "tests_dir": "tests",
        },
        "summary": {
            "core_blueprint_entries": len(rows),
            "route_heavy_surfaces": len(route_heavy),
            "route_heavy_without_direct_contract_tests": len(uncovered_route_heavy),
        },
        "recommended_next_slice": asdict(recommended) if recommended else None,
        "top_uncovered_route_heavy_surfaces": [asdict(row) for row in uncovered_route_heavy[:12]],
        "route_heavy_surfaces": [asdict(row) for row in route_heavy],
    }
    return inventory



def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    recommended = data["recommended_next_slice"]
    route_heavy_gap_open = summary["route_heavy_without_direct_contract_tests"] > 0
    recommendation_reason = (
        "hohe Route-Dichte + fehlende direkte Contract-Abdeckung auf aktiver Runtime-Surface"
        if route_heavy_gap_open
        else "direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle bei sonst vollständig kontraktabgedeckten route-starken Surfaces"
    )
    decision_line = (
        "- Nächster echter Repair-Slice soll von diesem Inventar auf eine route-starke, bislang nicht direkt kontraktabgedeckte Runtime-Surface gehen."
        if route_heavy_gap_open
        else "- Nächster echter Repair-Slice soll von diesem Inventar auf die nächste direkt ungetestete Runtime-Surface unterhalb der Route-Heavy-Schwelle gehen."
    )
    lines = [
        "# PS Core Runtime / Contract Inventory — 2026-04-04",
        "",
        "## Ziel",
        "- fehlendes Runtime-/Contract-Inventar im aktiven Core-Worktree aus realem Code nachziehen",
        "- route-starke Registry-Surfaces gegen direkte Contract-Tests schneiden",
        "- genau **einen** nächsten Repair-Slice aus Worktree-Wahrheit ableiten",
        "",
        "## Summary",
        f"- Core-Registry-Einträge geprüft: **{summary['core_blueprint_entries']}**",
        f"- Route-starke Surfaces (>=5 Routes): **{summary['route_heavy_surfaces']}**",
        f"- Route-starke Surfaces ohne direkte Contract-Tests: **{summary['route_heavy_without_direct_contract_tests']}**",
        "",
        "## Empfohlener nächster Slice",
    ]

    if recommended:
        module_path = str(recommended["module_path"])
        lines.extend(
            [
                f"- **Surface:** `{module_path}`",
                f"- **Source:** `{recommended['source_path']}`",
                f"- **Routes:** **{recommended['route_count']}**",
                f"- **Direkte Testdateien:** {recommended['direct_test_files'] or 'keine'}",
                f"- **Direkte Contract-Tests:** {recommended['direct_contract_test_files'] or 'keine'}",
                f"- **Ableitung:** {recommendation_reason}",
                f"- **Vorgeschlagener Slice:** `Direkte Contract-Baseline für {module_path}`",
                f"- **Success Signal:** `{module_path}` ist auf Request-/Response-/Fehlerpfaden fokussiert kontraktabgedeckt, ohne Live-/Install-Schritt",
            ]
        )
    else:
        lines.append("- Kein neuer Slice abgeleitet")

    lines.extend(["", "## Top uncovered route-heavy surfaces"])
    for row in data["top_uncovered_route_heavy_surfaces"]:
        lines.append(
            f"- `{row['module_path']}` — routes={row['route_count']}, "
            f"contract_tests={len(row['direct_contract_test_files'])}, source=`{row['source_path']}`"
        )

    lines.extend(
        [
            "",
            "## Entscheidung",
            "- Voice-Phrase-Parität wird **nicht** weiter blind vorgezogen.",
            decision_line,
            (
                f"- Auf Basis der aktuellen Worktree-Wahrheit ist `{recommended['module_path']}` der schärfste nächste Kandidat."
                if recommended
                else "- Der aktuelle Worktree liefert keinen weiteren priorisierten Kandidaten."
            ),
            "",
        ]
    )
    return "\n".join(lines)



def main() -> int:
    parser = argparse.ArgumentParser(description="Build the active PilotSuite Core runtime/contract inventory")
    parser.add_argument("--repo", default="/config/clawd/team/worktrees/pilotsuite-styx-core-current")
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    parser.add_argument("--stdout-json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    data = build_inventory(repo_root)

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
