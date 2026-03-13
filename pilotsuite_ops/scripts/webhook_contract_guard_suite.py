#!/usr/bin/env python3
"""PS-DAI-055: Webhook contract guard suite runner.

Why:
- We already ship two lightweight, dependency-free guards:
  - PS-DAI-050: OpenAPI webhook example guard (Core↔HA)
  - PS-QA-053: target error-code drift guard (OpenAPI + HA runtime + schema)
- This suite runs both in one go and produces a single, audit-friendly report + exit code.

Exit codes:
  0 = PASS (all guards pass)
  2 = FAIL (any guard fails / cannot run)

Dependency-free: Python stdlib only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
import sys


@dataclass(frozen=True)
class GuardResult:
    name: str
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    report_path: Path | None


def _workspace_root() -> Path:
    # /config/clawd/pilotsuite_ops/scripts/<this_file>
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _truncate(text: str, *, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n... (truncated)\n"


def _run_guard(*, name: str, argv: list[str], report_path: Path | None) -> GuardResult:
    try:
        proc = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            check=False,
        )
        return GuardResult(
            name=name,
            argv=argv,
            exit_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            report_path=report_path,
        )
    except Exception as exc:  # noqa: BLE001
        return GuardResult(
            name=name,
            argv=argv,
            exit_code=2,
            stdout="",
            stderr=f"runner_error: {exc}",
            report_path=report_path,
        )


def _render_suite_report(*, suite_name: str, results: list[GuardResult]) -> str:
    overall = "PASS"
    if any(r.exit_code != 0 for r in results):
        overall = "FAIL"

    lines: list[str] = [
        f"# {suite_name} — Webhook Contract Guard Suite",
        "",
        f"- generated_at_utc: `{_utc_now()}`",
        f"- result: **{overall}**",
        "",
        "## Sub-Guards",
        "",
    ]

    for r in results:
        cmd = " ".join(shlex.quote(a) for a in r.argv)
        lines.extend(
            [
                f"### {r.name}",
                "",
                f"- exit_code: `{r.exit_code}`",
                f"- command: `{cmd}`",
                f"- report_path: `{r.report_path}`" if r.report_path else "- report_path: (none)",
                "",
            ]
        )

        if r.stdout.strip():
            lines.append("#### stdout (truncated)")
            lines.append("")
            lines.append("```\n" + _truncate(r.stdout).rstrip() + "\n```")
            lines.append("")

        if r.stderr.strip():
            lines.append("#### stderr (truncated)")
            lines.append("")
            lines.append("```\n" + _truncate(r.stderr).rstrip() + "\n```")
            lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- This suite does not parse YAML; it delegates to dependency-free, text-based guards.",
            "- Intended use: quick preflight / CI lint step before release gates.",
        ]
    )

    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    root = _workspace_root()

    ap = argparse.ArgumentParser(description="PS-DAI-055: Webhook contract guard suite runner")
    ap.add_argument(
        "--out-md",
        default=str(root / "pilotsuite_ops/reports/PS-DAI-055_WEBHOOK_CONTRACT_GUARD_SUITE.md"),
        help="Markdown suite report output path",
    )

    # Forwarded options (keep minimal; suite is mainly orchestration)
    ap.add_argument(
        "--core-openapi",
        default=str(root / "team/repos/pilotsuite-styx-core/docs/openapi.yaml"),
        help="Path to Core OpenAPI YAML",
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
        "--codes-400",
        default="missing_type,missing_data,unknown_type",
        help="Comma-separated error codes expected as 400 examples (OpenAPI example guard)",
    )
    ap.add_argument(
        "--codes-401",
        default="invalid_token,legacy_header_sunset",
        help="Comma-separated error codes expected as 401 examples (OpenAPI example guard)",
    )
    ap.add_argument(
        "--codes",
        default="missing_type,missing_data,unknown_type,invalid_token,legacy_header_sunset",
        help="Comma-separated target codes (drift guard)",
    )

    args = ap.parse_args(argv)

    out_md = Path(args.out_md).expanduser().resolve()
    out_md.parent.mkdir(parents=True, exist_ok=True)

    # Keep subreports next to the suite report for auditability.
    sub_openapi_md = out_md.parent / "PS-DAI-055_subreport_openapi_example_guard.md"
    sub_drift_md = out_md.parent / "PS-DAI-055_subreport_contract_drift_guard.md"

    openapi_guard = root / "pilotsuite_ops" / "scripts" / "webhook_openapi_example_guard.py"
    drift_guard = root / "pilotsuite_ops" / "scripts" / "webhook_contract_drift_guard.py"

    py = sys.executable or "python3"

    results: list[GuardResult] = []

    results.append(
        _run_guard(
            name="PS-DAI-050 webhook_openapi_example_guard",
            argv=[
                py,
                str(openapi_guard),
                "--core-openapi",
                str(Path(args.core_openapi).expanduser().resolve()),
                "--ha-openapi",
                str(Path(args.ha_openapi).expanduser().resolve()),
                "--codes-400",
                args.codes_400,
                "--codes-401",
                args.codes_401,
                "--out-md",
                str(sub_openapi_md),
            ],
            report_path=sub_openapi_md,
        )
    )

    results.append(
        _run_guard(
            name="PS-QA-053 webhook_contract_drift_guard",
            argv=[
                py,
                str(drift_guard),
                "--core-openapi",
                str(Path(args.core_openapi).expanduser().resolve()),
                "--ha-openapi",
                str(Path(args.ha_openapi).expanduser().resolve()),
                "--ha-runtime",
                str(Path(args.ha_runtime).expanduser().resolve()),
                "--schema",
                str(Path(args.schema).expanduser().resolve()),
                "--codes",
                args.codes,
                "--out-md",
                str(sub_drift_md),
            ],
            report_path=sub_drift_md,
        )
    )

    suite_name = "PS-DAI-055"
    out_md.write_text(
        _render_suite_report(suite_name=suite_name, results=results),
        encoding="utf-8",
    )

    overall_fail = any(r.exit_code != 0 for r in results)
    print(f"[ps-dai-055] suite report: {out_md}")
    print(f"[ps-dai-055] result: {'FAIL' if overall_fail else 'PASS'}")

    for r in results:
        if r.exit_code != 0:
            print(f"[ps-dai-055] FAIL: {r.name} exit_code={r.exit_code}")

    return 2 if overall_fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
