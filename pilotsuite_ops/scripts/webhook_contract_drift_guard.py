#!/usr/bin/env python3
"""PS-QA-053: Lightweight webhook contract drift guard.

Checks that target error codes exist across:
- Core OpenAPI
- HA OpenAPI
- HA runtime implementation
- Contract response schema

Exit codes:
  0 = PASS (no drift for target codes)
  2 = FAIL (drift found / required files unreadable)

Dependency-free: Python stdlib only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


DEFAULT_CODES = [
    "missing_type",
    "missing_data",
    "unknown_type",
    "invalid_token",
    "legacy_header_sunset",
]


@dataclass(frozen=True)
class Source:
    name: str
    path: Path


def _workspace_root() -> Path:
    # /config/clawd/pilotsuite_ops/scripts/<this_file>
    return Path(__file__).resolve().parents[2]


def _compile_code_pattern(code: str) -> re.Pattern[str]:
    # Match as standalone token-like text (avoid partial substring matches).
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(code)}(?![A-Za-z0-9_])")


def _check_source(source: Source, codes: list[str]) -> tuple[list[str], list[str], str | None]:
    try:
        text = source.path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - keep dependency-free + broad for IO errors
        return [], list(codes), f"read_error: {exc}"

    present: list[str] = []
    missing: list[str] = []
    for code in codes:
        if _compile_code_pattern(code).search(text):
            present.append(code)
        else:
            missing.append(code)

    return present, missing, None


def _render_md_report(
    *,
    sources: list[Source],
    codes: list[str],
    checked: dict[str, dict[str, object]],
    result: str,
) -> str:
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    lines: list[str] = [
        "# PS-QA-053 — Webhook Contract Drift Guard Report",
        "",
        f"- generated_at_utc: `{utc_now}`",
        f"- result: **{result}**",
        "",
        "## Zielcodes",
        "",
        f"- {', '.join(f'`{c}`' for c in codes)}",
        "",
        "## Geprüfte Quellen",
        "",
    ]

    for src in sources:
        lines.append(f"- {src.name}: `{src.path}`")

    lines.extend(["", "## Ergebnis je Quelle", ""])

    for src in sources:
        info = checked[src.name]
        read_error = info.get("read_error")
        present = info.get("present", [])
        missing = info.get("missing", [])

        lines.append(f"### {src.name}")
        if read_error:
            lines.append("")
            lines.append(f"- status: FAIL (Datei nicht lesbar)")
            lines.append(f"- detail: `{read_error}`")
            lines.append("")
            continue

        lines.append("")
        lines.append(f"- present ({len(present)}/{len(codes)}): {', '.join(f'`{c}`' for c in present) if present else '(none)'}")
        if missing:
            lines.append(f"- missing ({len(missing)}): {', '.join(f'`{c}`' for c in missing)}")
        else:
            lines.append("- missing (0): (none)")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    root = _workspace_root()

    ap = argparse.ArgumentParser(description="Lightweight webhook target-code drift guard (PS-QA-053)")
    ap.add_argument(
        "--core-openapi",
        default=str(root / "team/repos/pilotsuite-styx-core/docs/openapi.yaml"),
        help="Path to core OpenAPI YAML",
    )
    ap.add_argument(
        "--ha-openapi",
        default=str(root / "team/repos/pilotsuite-styx-ha/docs/openapi.yaml"),
        help="Path to HA OpenAPI YAML",
    )
    ap.add_argument(
        "--ha-runtime",
        default=str(root / "team/repos/pilotsuite-styx-ha/custom_components/copilot_ha/webhook.py"),
        help="Path to HA runtime webhook implementation",
    )
    ap.add_argument(
        "--schema",
        default=str(root / "pilotsuite_ops/schemas/webhook_response.schema.json"),
        help="Path to webhook response contract schema",
    )
    ap.add_argument(
        "--codes",
        default=",".join(DEFAULT_CODES),
        help="Comma-separated target codes to assert across all sources",
    )
    ap.add_argument(
        "--out-md",
        default=str(root / "pilotsuite_ops/reports/PS-QA-053_CONTRACT_DRIFT_GUARD.md"),
        help="Optional Markdown report output path",
    )

    args = ap.parse_args(argv)

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    if not codes:
        print("[ps-qa-053] FAIL: no target codes provided", file=sys.stderr)
        return 2

    sources = [
        Source("core_openapi", Path(args.core_openapi).expanduser().resolve()),
        Source("ha_openapi", Path(args.ha_openapi).expanduser().resolve()),
        Source("ha_runtime", Path(args.ha_runtime).expanduser().resolve()),
        Source("response_schema", Path(args.schema).expanduser().resolve()),
    ]

    checked: dict[str, dict[str, object]] = {}
    has_drift = False

    for src in sources:
        present, missing, read_error = _check_source(src, codes)
        checked[src.name] = {
            "present": present,
            "missing": missing,
            "read_error": read_error,
        }

        if read_error or missing:
            has_drift = True

    result = "FAIL" if has_drift else "PASS"
    print(f"[ps-qa-053] Drift guard result: {result}")

    for src in sources:
        info = checked[src.name]
        if info["read_error"]:
            print(f"[ps-qa-053] {src.name}: READ_ERROR -> {info['read_error']}")
            continue
        missing = info["missing"]
        if missing:
            print(f"[ps-qa-053] {src.name}: missing {', '.join(missing)}")
        else:
            print(f"[ps-qa-053] {src.name}: ok ({len(info['present'])}/{len(codes)})")

    out_md = Path(args.out_md).expanduser().resolve() if args.out_md else None
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(
            _render_md_report(
                sources=sources,
                codes=codes,
                checked=checked,
                result=result,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"[ps-qa-053] markdown report: {out_md}")

    return 2 if has_drift else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
