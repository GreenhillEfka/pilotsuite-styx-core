#!/usr/bin/env python3
"""PS-DAI-050: Webhook OpenAPI example guard (Core↔HA).

Goal: catch contract drift in the *webhook endpoint section* of OpenAPI specs,
without requiring a YAML parser (dependency-free, stdlib only).

What it checks (per OpenAPI file):
- The `/api/webhook/{webhook_id}` path exists.
- The endpoint block references contract schemas.
- The requestBody and key responses reference the expected schema component refs.
- Required error-code examples exist and contain minimal required fields.

Exit codes:
  0 = PASS
  2 = FAIL (drift found)

Note: This is a *lint/guard*, not a semantic YAML validator.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


DEFAULT_CODES_400 = ["missing_type", "missing_data", "unknown_type"]
DEFAULT_CODES_401 = ["invalid_token", "legacy_header_sunset"]


@dataclass(frozen=True)
class Finding:
    level: str  # PASS|FAIL|WARN
    message: str


def _workspace_root() -> Path:
    # /config/clawd/pilotsuite_ops/scripts/<this_file>
    return Path(__file__).resolve().parents[2]


def _read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except Exception as exc:  # noqa: BLE001
        return None, f"read_error: {exc}"


def _slice_webhook_block(text: str) -> tuple[str | None, str | None]:
    # Path entries are at indentation level 2 in both specs we ship.
    anchor = "  /api/webhook/{webhook_id}:"
    start = text.find(anchor)
    if start < 0:
        return None, "missing webhook path: /api/webhook/{webhook_id}"

    # end at next path entry at same indentation
    rest = text[start + len(anchor) :]
    m = re.search(r"\n\s{2}/", rest)
    end = start + len(anchor) + (m.start() if m else len(rest))

    return text[start:end], None


def _has_pattern(block: str, pattern: str) -> bool:
    return re.search(pattern, block, flags=re.MULTILINE) is not None


def _find_example_window(block: str, code: str, window_lines: int = 50) -> list[str] | None:
    lines = block.splitlines()
    # Find the line containing the example key (e.g. "missing_type:")
    for i, line in enumerate(lines):
        if re.match(rf"^\s+{re.escape(code)}:\s*$", line):
            return lines[i : i + window_lines]
    return None


def _check_example_block(lines: list[str], code: str) -> list[Finding]:
    joined = "\n".join(lines)
    findings: list[Finding] = []

    # Minimal assertions
    if not re.search(r"\n\s*ok:\s*false\b", joined):
        findings.append(Finding("FAIL", f"example `{code}`: missing `ok: false`"))

    if not re.search(rf"\n\s*code:\s*{re.escape(code)}\b", joined):
        findings.append(Finding("FAIL", f"example `{code}`: missing `error.code: {code}`"))

    if not re.search(r"\n\s*message:\s*", joined):
        findings.append(Finding("WARN", f"example `{code}`: missing `error.message` (not fatal)"))

    return findings


def _check_openapi_file(
    *,
    name: str,
    openapi_path: Path,
    schema_root: Path,
    codes_400: list[str],
    codes_401: list[str],
) -> tuple[list[Finding], str | None]:
    text, err = _read_text(openapi_path)
    if err:
        return [Finding("FAIL", f"{name}: {err}")], err

    assert text is not None

    block, block_err = _slice_webhook_block(text)
    if block_err:
        return [Finding("FAIL", f"{name}: {block_err}")], block_err

    assert block is not None

    findings: list[Finding] = []

    # Contract schema references (non-fatal if missing, but should exist)
    for rel in [
        "pilotsuite_ops/schemas/webhook_envelope.schema.json",
        "pilotsuite_ops/schemas/webhook_response.schema.json",
    ]:
        if rel not in block:
            findings.append(Finding("WARN", f"{name}: webhook block missing contract schema reference `{rel}`"))
        # Existence check (only if it is a local path we expect to exist)
        local = schema_root / "pilotsuite_ops" / "schemas" / Path(rel).name
        if not local.exists():
            findings.append(Finding("WARN", f"{name}: local schema file not found: `{local}`"))

    # Expected $refs
    expected_patterns = [
        r"\$ref:\s*'#/components/schemas/WebhookEnvelope'",
        r"\$ref:\s*'#/components/schemas/WebhookSuccessResponse'",
        r"\$ref:\s*'#/components/schemas/WebhookErrorResponse'",
    ]
    for pat in expected_patterns:
        if not _has_pattern(block, pat):
            findings.append(Finding("FAIL", f"{name}: missing expected ref in webhook endpoint block: /{pat}/"))

    # Required response codes
    for status in ["'200':", "'400':", "'401':"]:
        if status not in block:
            findings.append(Finding("FAIL", f"{name}: missing response status {status} in webhook endpoint"))

    # Example payload checks
    for code in codes_400 + codes_401:
        win = _find_example_window(block, code)
        if win is None:
            findings.append(Finding("FAIL", f"{name}: missing OpenAPI example block for `{code}`"))
            continue
        findings.extend(_check_example_block(win, code))

    if not findings:
        findings.append(Finding("PASS", f"{name}: webhook OpenAPI example guard passed"))

    return findings, None


def _render_report(*, core_findings: list[Finding], ha_findings: list[Finding]) -> str:
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    def fmt(findings: list[Finding]) -> list[str]:
        out: list[str] = []
        for f in findings:
            out.append(f"- {f.level}: {f.message}")
        return out

    # Determine overall
    all_findings = core_findings + ha_findings
    overall = "PASS"
    if any(f.level == "FAIL" for f in all_findings):
        overall = "FAIL"

    lines: list[str] = [
        "# PS-DAI-050 — Webhook OpenAPI Example Guard Report",
        "",
        f"- generated_at_utc: `{utc_now}`",
        f"- result: **{overall}**",
        "",
        "## Core OpenAPI",
        "",
        *fmt(core_findings),
        "",
        "## HA OpenAPI",
        "",
        *fmt(ha_findings),
        "",
        "## Notes",
        "",
        "- This guard is text-based (no YAML parser). It is intentionally conservative and focuses on the webhook endpoint block.",
        "- For error-code presence across OpenAPI + runtime + schema, see `pilotsuite_ops/scripts/webhook_contract_drift_guard.py` (PS-QA-053).",
    ]

    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    root = _workspace_root()

    ap = argparse.ArgumentParser(description="PS-DAI-050: Webhook OpenAPI example guard")
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
        "--codes-400",
        default=",".join(DEFAULT_CODES_400),
        help="Comma-separated error codes expected as 400 examples",
    )
    ap.add_argument(
        "--codes-401",
        default=",".join(DEFAULT_CODES_401),
        help="Comma-separated error codes expected as 401 examples",
    )
    ap.add_argument(
        "--out-md",
        default=str(root / "pilotsuite_ops/reports/PS-DAI-050_WEBHOOK_OPENAPI_EXAMPLE_GUARD.md"),
        help="Markdown report output path",
    )

    args = ap.parse_args(argv)

    codes_400 = [c.strip() for c in args.codes_400.split(",") if c.strip()]
    codes_401 = [c.strip() for c in args.codes_401.split(",") if c.strip()]

    core_path = Path(args.core_openapi).expanduser().resolve()
    ha_path = Path(args.ha_openapi).expanduser().resolve()

    core_findings, _ = _check_openapi_file(
        name="core_openapi",
        openapi_path=core_path,
        schema_root=root,
        codes_400=codes_400,
        codes_401=codes_401,
    )
    ha_findings, _ = _check_openapi_file(
        name="ha_openapi",
        openapi_path=ha_path,
        schema_root=root,
        codes_400=codes_400,
        codes_401=codes_401,
    )

    report_path = Path(args.out_md).expanduser().resolve() if args.out_md else None
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_render_report(core_findings=core_findings, ha_findings=ha_findings), encoding="utf-8")
        print(f"[ps-dai-050] report: {report_path}")

    all_findings = core_findings + ha_findings
    has_fail = any(f.level == "FAIL" for f in all_findings)
    print(f"[ps-dai-050] result: {'FAIL' if has_fail else 'PASS'}")

    for f in all_findings:
        if f.level == "FAIL":
            print(f"[ps-dai-050] FAIL: {f.message}")

    return 2 if has_fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
