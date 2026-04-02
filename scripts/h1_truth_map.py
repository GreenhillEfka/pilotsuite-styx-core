#!/usr/bin/env python3
"""Generate a canonical PilotSuite Core H1 truth map.

This script intentionally uses only the Python standard library so it can run
inside constrained runtime environments.

Outputs:
- JSON machine-readable truth map
- Markdown human-readable report

Focus:
- active worktree vs runtime tree
- blueprint registry vs runtime blueprint imports
- legacy doc markers
- OpenAPI file footprint
- hard blockers in runtime wiring (e.g. syntax errors)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import py_compile
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class FileFact:
    path: str
    exists: bool
    size_bytes: int | None = None


def count_python_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.rglob("*.py") if p.is_file())


def openapi_path_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("  /"):
                count += 1
    return count


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def detect_legacy_markers(path: Path) -> dict[str, Any]:
    text = read_text(path)
    lowered = text.lower()
    return {
        "path": str(path),
        "exists": path.exists(),
        "legacy": "legacy" in lowered,
        "historical": "historical" in lowered,
        "outdated": "outdated" in lowered or "veraltet" in lowered,
        "canonical_truth_mentions": "canonical api truth" in lowered or "kanon" in lowered,
    }


def load_blueprint_config(path: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("h1_blueprints_config", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load blueprint config from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    core = getattr(module, "CORE_API_BLUEPRINTS")
    external = getattr(module, "EXTERNAL_BLUEPRINTS")
    return {
        "core_count": len(core),
        "external_count": len(external),
        "core_entries": [list(item) for item in core],
        "external_entries": [list(item) for item in external],
    }


def parse_runtime_blueprint_imports(path: Path) -> list[dict[str, str]]:
    text = read_text(path)
    pattern = re.compile(
        r"^from\s+(copilot_core(?:\.[A-Za-z0-9_]+)+)\s+import\s+(.+?)\s+as\s+([A-Za-z0-9_]+)",
        re.MULTILINE,
    )
    imports: list[dict[str, str]] = []
    for module_path, imported_name, alias in pattern.findall(text):
        imports.append(
            {
                "module_path": module_path,
                "imported_name": imported_name.strip(),
                "alias": alias,
            }
        )
    return imports


def py_compile_status(path: Path) -> dict[str, Any]:
    try:
        py_compile.compile(str(path), doraise=True)
        return {"ok": True, "error": None}
    except py_compile.PyCompileError as exc:
        return {"ok": False, "error": str(exc)}


def build_truth_map(repo_root: Path) -> dict[str, Any]:
    runtime_api_dir = repo_root / "copilot_core" / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "api" / "v1"
    repo_api_dir = repo_root / "copilot_core" / "api" / "v1"
    blueprints_config = repo_root / "copilot_core" / "blueprints_config.py"
    runtime_blueprint = runtime_api_dir / "blueprint.py"
    runtime_core_setup = repo_root / "copilot_core" / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "core_setup.py"
    docs_openapi = repo_root / "docs" / "openapi.yaml"
    repo_openapi = repo_root / "copilot_core" / "docs" / "openapi.yaml"
    api_reference = repo_root / "docs" / "API_REFERENCE.md"
    api_complete = repo_root / "docs" / "API_COMPLETE.md"

    blueprint_config = load_blueprint_config(blueprints_config)
    runtime_imports = parse_runtime_blueprint_imports(runtime_blueprint)
    runtime_import_modules = {entry["module_path"] for entry in runtime_imports}
    config_modules = {entry[0] for entry in blueprint_config["core_entries"]}

    summary = {
        "repo_root": str(repo_root),
        "core_truth": {
            "active_worktree": str(repo_root),
            "runtime_tree": str(runtime_api_dir.parent.parent),
            "repo_api_dir": str(repo_api_dir),
            "runtime_api_dir": str(runtime_api_dir),
        },
        "counts": {
            "repo_api_python_files": count_python_files(repo_api_dir),
            "runtime_api_python_files": count_python_files(runtime_api_dir),
            "blueprints_config_core_entries": blueprint_config["core_count"],
            "blueprints_config_external_entries": blueprint_config["external_count"],
            "runtime_blueprint_imports": len(runtime_imports),
            "docs_openapi_paths": openapi_path_count(docs_openapi),
            "repo_openapi_paths": openapi_path_count(repo_openapi),
        },
        "files": {
            "blueprints_config": asdict(FileFact(str(blueprints_config), blueprints_config.exists(), blueprints_config.stat().st_size if blueprints_config.exists() else None)),
            "runtime_blueprint": asdict(FileFact(str(runtime_blueprint), runtime_blueprint.exists(), runtime_blueprint.stat().st_size if runtime_blueprint.exists() else None)),
            "runtime_core_setup": asdict(FileFact(str(runtime_core_setup), runtime_core_setup.exists(), runtime_core_setup.stat().st_size if runtime_core_setup.exists() else None)),
            "docs_openapi": asdict(FileFact(str(docs_openapi), docs_openapi.exists(), docs_openapi.stat().st_size if docs_openapi.exists() else None)),
            "repo_openapi": asdict(FileFact(str(repo_openapi), repo_openapi.exists(), repo_openapi.stat().st_size if repo_openapi.exists() else None)),
        },
        "doc_truth_markers": {
            "api_reference": detect_legacy_markers(api_reference),
            "api_complete": detect_legacy_markers(api_complete),
        },
        "runtime_validity": {
            "core_setup_py_compile": py_compile_status(runtime_core_setup),
        },
        "diffs": {
            "in_config_not_in_runtime_blueprint_imports": sorted(config_modules - runtime_import_modules),
            "in_runtime_blueprint_imports_not_in_config": sorted(runtime_import_modules - config_modules),
        },
        "samples": {
            "config_first_15": blueprint_config["core_entries"][:15],
            "runtime_imports_first_20": runtime_imports[:20],
        },
    }

    blockers: list[dict[str, str]] = []
    if not summary["runtime_validity"]["core_setup_py_compile"]["ok"]:
        blockers.append(
            {
                "severity": "critical",
                "area": "runtime_wiring",
                "fact": "core_setup.py does not compile",
                "path": str(runtime_core_setup),
            }
        )
    if summary["counts"]["repo_api_python_files"] < summary["counts"]["runtime_api_python_files"]:
        blockers.append(
            {
                "severity": "high",
                "area": "truth_split",
                "fact": "runtime API tree is much larger than repo-level API tree; runtime tree must be treated as primary wiring surface",
                "path": str(runtime_api_dir),
            }
        )
    if summary["doc_truth_markers"]["api_reference"]["legacy"]:
        blockers.append(
            {
                "severity": "medium",
                "area": "documentation",
                "fact": "API_REFERENCE.md explicitly marks itself as legacy/partially outdated",
                "path": str(api_reference),
            }
        )
    if summary["doc_truth_markers"]["api_complete"]["legacy"]:
        blockers.append(
            {
                "severity": "medium",
                "area": "documentation",
                "fact": "API_COMPLETE.md explicitly marks itself as legacy/historical",
                "path": str(api_complete),
            }
        )
    summary["blockers"] = blockers
    return summary


def render_markdown(data: dict[str, Any]) -> str:
    counts = data["counts"]
    runtime_compile = data["runtime_validity"]["core_setup_py_compile"]
    blockers = data["blockers"]

    lines = [
        "# H1 Truth Map — PilotSuite Core",
        "",
        "## Summary",
        f"- Active worktree truth: `{data['core_truth']['active_worktree']}`",
        f"- Runtime API tree Python files: **{counts['runtime_api_python_files']}**",
        f"- Repo-level API tree Python files: **{counts['repo_api_python_files']}**",
        f"- Central blueprint config entries: **{counts['blueprints_config_core_entries']}** core + **{counts['blueprints_config_external_entries']}** external",
        f"- Runtime blueprint imports: **{counts['runtime_blueprint_imports']}**",
        f"- `docs/openapi.yaml` path count: **{counts['docs_openapi_paths']}**",
        f"- `copilot_core/docs/openapi.yaml` path count: **{counts['repo_openapi_paths']}**",
        "",
        "## Canonical Truth Decision",
        "- Primary API/runtime truth is the active Core worktree plus runtime wiring under `copilot_core/rootfs/usr/src/app/copilot_core/...`.",
        "- Repo-level `copilot_core/api/v1` is not sufficient as sole truth source.",
        "- `docs/API_REFERENCE.md` and `docs/API_COMPLETE.md` are reference-only, not contract truth.",
        "",
        "## Runtime Wiring Validity",
        f"- `core_setup.py` compiles: **{'YES' if runtime_compile['ok'] else 'NO'}**",
    ]
    if runtime_compile["error"]:
        lines += ["", "```", runtime_compile["error"], "```"]

    lines += ["", "## Config vs Runtime Diffs"]
    lines.append(f"- In config, not imported by runtime blueprint: **{len(data['diffs']['in_config_not_in_runtime_blueprint_imports'])}** modules")
    lines.append(f"- In runtime blueprint imports, not in config: **{len(data['diffs']['in_runtime_blueprint_imports_not_in_config'])}** modules")

    lines += ["", "## Blockers"]
    if blockers:
        for blocker in blockers:
            lines.append(f"- **{blocker['severity'].upper()}** {blocker['area']}: {blocker['fact']} (`{blocker['path']}`)")
    else:
        lines.append("- None detected")

    lines += ["", "## Recommendation", "1. Treat H1 as verified truth capture complete only after this report is generated and reviewed.", "2. Fix runtime wiring blocker(s) before claiming integrated iteration stability.", "3. Use this report to drive H2 blueprint/OpenAPI reconciliation."]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate H1 truth map for PilotSuite Core")
    parser.add_argument("--repo", default="/config/clawd/team/worktrees/pilotsuite-styx-core-current", help="Path to repo root")
    parser.add_argument("--json-out", default=None, help="Write JSON report to this path")
    parser.add_argument("--md-out", default=None, help="Write Markdown report to this path")
    parser.add_argument("--stdout-json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    data = build_truth_map(repo_root)

    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.md_out:
        md_path = Path(args.md_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(data) + "\n", encoding="utf-8")

    if args.stdout_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
