"""Diagnostics Contract v0.1 (minimal kernel implementation).

Privacy-first, bounded diagnostics bundle generator.

This module is intentionally small and dependency-free.

Contract: docs/module_specs/diagnostics_contract_v0.1.md
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import io
import json
import os
import re
import time
import zipfile
from datetime import datetime, timezone
from typing import Any, Callable

CONTRACT = "diagnostics_contract"
CONTRACT_VERSION = "0.1"

LEVELS = ("minimal", "standard", "deep")

# --- Redaction / sanitization (best-effort, strict-by-default) ---

_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RE_PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}(?!\d)")
_RE_IPV4 = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
_RE_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
)
_RE_BEARER = re.compile(r"(?i)(bearer\s+)(\S+)")
_RE_URL_CREDS = re.compile(r"(?i)(https?://)([^\s:/]+):([^\s@/]+)@")
_RE_URL = re.compile(r"https?://[^\s]+")

# Token-like long strings (avoid nuking stack traces: require mixed charset and length)
_RE_SECRETISH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9])")


@dataclasses.dataclass
class RedactionStats:
    redacted_email: int = 0
    redacted_phone: int = 0
    redacted_ip: int = 0
    redacted_secret: int = 0
    lines_truncated: int = 0


def _now_ms() -> int:
    return int(time.time() * 1000)


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def sanitize_text(text: str, *, stats: RedactionStats | None = None, max_line_chars: int = 2000) -> str:
    """Sanitize free text for bundle persistence.

    Strict: remove obvious PII/secrets. Clamp line length.
    """

    if not text:
        return ""

    def _count_sub(regex: re.Pattern[str], repl: str, s: str, field: str) -> str:
        nonlocal stats
        if stats is None:
            return regex.sub(repl, s)
        new_s, n = regex.subn(repl, s)
        if n:
            setattr(stats, field, getattr(stats, field) + n)
        return new_s

    # Redact inline URL credentials first.
    text = _count_sub(_RE_URL_CREDS, r"\1**REDACTED**:**REDACTED**@", text, "redacted_secret")

    # Remove URL query/fragment; keep host/path but avoid leaking tokens.
    def _url_repl(m: re.Match[str]) -> str:
        url = m.group(0)
        base = url.split("?", 1)[0].split("#", 1)[0]
        return base

    text = _RE_URL.sub(_url_repl, text)

    text = _count_sub(_RE_BEARER, r"\1[REDACTED_SECRET]", text, "redacted_secret")
    text = _count_sub(_RE_JWT, "[REDACTED_SECRET]", text, "redacted_secret")

    # Very rough secret-ish matcher (may over-redact). Only after URLs/JWT.
    text = _count_sub(_RE_SECRETISH, "[REDACTED_SECRET]", text, "redacted_secret")

    text = _count_sub(_RE_EMAIL, "[REDACTED_EMAIL]", text, "redacted_email")
    text = _count_sub(_RE_PHONE, "[REDACTED_PHONE]", text, "redacted_phone")

    # IPs: mask RFC1918-ish by default, otherwise redact.
    def _ip_repl(m: re.Match[str]) -> str:
        ip = m.group(0)
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                a, b, _, _ = [int(p) for p in parts]
                if a == 10 or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31):
                    return f"{a}.{b}.x.x"
            except Exception:
                pass
        return "[REDACTED_IP]"

    if stats is None:
        text = _RE_IPV4.sub(_ip_repl, text)
    else:
        new_text, n = _RE_IPV4.subn(_ip_repl, text)
        stats.redacted_ip += n
        text = new_text

    # Clamp line length.
    out_lines: list[str] = []
    for line in text.splitlines():
        if len(line) > max_line_chars:
            if stats is not None:
                stats.lines_truncated += 1
            out_lines.append(line[: max_line_chars - 20] + "…(truncated)…")
        else:
            out_lines.append(line)

    return "\n".join(out_lines)


class Pseudonymizer:
    """Stable local pseudonyms (do not include salt in bundle)."""

    def __init__(self, *, salt: bytes, prefix: str):
        self._salt = salt
        self._prefix = prefix

    def __call__(self, value: str) -> str:
        if value is None:
            return ""
        raw = value.encode("utf-8")
        digest = hmac.new(self._salt, raw, hashlib.sha256).hexdigest()[:16]
        return f"{self._prefix}_{digest}"


def _load_install_salt() -> tuple[str, bytes]:
    """Return (salt_id, salt_bytes).

    Uses /data/.install_uuid if present, otherwise creates one.
    """

    path = "/data/.install_uuid"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                salt_id = fh.read().strip() or "local-install"
        else:
            salt_id = hashlib.sha256(os.urandom(32)).hexdigest()
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(salt_id)
    except Exception:
        salt_id = "local-install"

    salt = hashlib.sha256(("diag:" + salt_id).encode("utf-8")).digest()
    return salt_id, salt


@dataclasses.dataclass
class Limits:
    max_total_bytes: int
    max_file_bytes: int
    max_files: int


def limits_for_level(level: str) -> Limits:
    if level == "minimal":
        return Limits(max_total_bytes=1_048_576, max_file_bytes=256_000, max_files=30)
    if level == "deep":
        return Limits(max_total_bytes=25_000_000, max_file_bytes=2_000_000, max_files=500)
    # standard
    return Limits(max_total_bytes=10_000_000, max_file_bytes=524_288, max_files=200)


class DiagnosticsBudget:
    def __init__(self, limits: Limits):
        self.limits = limits
        self.total_bytes = 0
        self.files = 0
        self.limits_hit: list[dict[str, Any]] = []

    def can_add_file(self) -> bool:
        return self.files < self.limits.max_files

    def _record(self, *, kind: str, path: str, detail: str) -> None:
        self.limits_hit.append({"kind": kind, "path": path, "detail": detail})

    def add_text(self, path: str, text: str) -> tuple[str, bool]:
        """Return possibly truncated text and whether it was truncated."""

        raw = text.encode("utf-8")
        if len(raw) <= self.limits.max_file_bytes:
            return text, False

        # Tail truncate (better for logs) + explain.
        keep = max(0, self.limits.max_file_bytes - 200)
        truncated = raw[-keep:]
        out = (
            "...(truncated; kept tail)\n"
            + truncated.decode("utf-8", errors="replace")
        )
        self._record(kind="truncate", path=path, detail=f"tail {keep} bytes")
        return out, True

    def account(self, path: str, content_bytes: int) -> bool:
        """Account bytes for a file; return True if accepted."""
        if not self.can_add_file():
            self._record(kind="max_files", path=path, detail="file skipped")
            return False
        if self.total_bytes + content_bytes > self.limits.max_total_bytes:
            self._record(kind="max_total_bytes", path=path, detail="file skipped")
            return False
        self.total_bytes += content_bytes
        self.files += 1
        return True


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def _best_effort_secret_scan(text: str) -> list[str]:
    hits: list[str] = []
    if re.search(r"(?i)bearer\s+\S+", text):
        hits.append("bearer_token")
    if _RE_JWT.search(text):
        hits.append("jwt")
    if _RE_EMAIL.search(text):
        hits.append("email")
    return hits


def build_bundle_zip(
    *,
    level: str,
    window_from_ts_ms: int,
    window_to_ts_ms: int,
    core_version: str,
    dev_log_items: list[dict[str, Any]],
    focus: dict[str, Any] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Create an in-memory diagnostics bundle zip.

    Returns (zip_bytes, manifest_dict).
    """

    if level not in LEVELS:
        level = "standard"

    limits = limits_for_level(level)
    budget = DiagnosticsBudget(limits)

    red_stats = RedactionStats()
    salt_id, salt = _load_install_salt()
    pseudonymize_ent = Pseudonymizer(salt=salt, prefix="ent")

    created_ts_ms = _now_ms()
    bundle_id = f"diag_{created_ts_ms}"

    contributors: list[dict[str, Any]] = []

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        def write_text(path: str, text: str) -> None:
            nonlocal budget
            text = text or ""
            text, _ = budget.add_text(path, text)
            data = text.encode("utf-8")
            if budget.account(path, len(data)):
                zf.writestr(path, data)

        def write_json(path: str, obj: Any) -> None:
            write_text(path, _json_dumps(obj) + "\n")

        # system/versions.json
        versions = {
            "core": {"version": core_version},
            "python": {"version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"},
        }
        write_json("system/versions.json", versions)

        # system/health.json (minimal)
        health = {"ok": True}
        write_json("system/health.json", health)

        # module: core
        module_name = "core"
        summary = {
            "status": "ok",
            "error_codes": [],
            "window": {"from_ts_ms": window_from_ts_ms, "to_ts_ms": window_to_ts_ms},
        }
        write_json(f"modules/{module_name}/summary.json", summary)

        # logs.txt (sanitized)
        # We do not include raw payloads; only sanitized JSON lines.
        log_lines: list[str] = []
        for item in dev_log_items:
            try:
                line = _json_dumps(item)
            except Exception:
                line = str(item)
            log_lines.append(sanitize_text(line, stats=red_stats))
        logs_txt = "\n".join(log_lines[-2000:]) + ("\n" if log_lines else "")
        if level == "minimal":
            # minimal: no logs, only counts.
            metrics = {"dev_log_items": len(dev_log_items)}
            write_json(f"modules/{module_name}/metrics.json", metrics)
        else:
            write_text(f"modules/{module_name}/logs.txt", logs_txt)
            metrics = {"dev_log_items": len(dev_log_items), "lines_included": min(len(log_lines), 2000)}
            write_json(f"modules/{module_name}/metrics.json", metrics)

        contributors.append(
            {
                "module": module_name,
                "version": core_version,
                "paths": [
                    "system/versions.json",
                    "system/health.json",
                    f"modules/{module_name}/summary.json",
                    f"modules/{module_name}/metrics.json",
                ]
                + ([] if level == "minimal" else [f"modules/{module_name}/logs.txt"]),
                "notes": "core dev logs tail (sanitized)",
            }
        )

        # redaction/report.json
        red_report = {
            "enabled": True,
            "mode": "strict",
            "pseudonymization": {
                "enabled": True,
                "method": "hmac-sha256",
                "salt_id": salt_id,
                "example": {"entity_id": pseudonymize_ent("light.kitchen")},
            },
            "stats": dataclasses.asdict(red_stats),
        }
        write_json("redaction/report.json", red_report)

        # manifest.json (written near end, but budget needs to include it too)
        manifest: dict[str, Any] = {
            "contract": CONTRACT,
            "contract_version": CONTRACT_VERSION,
            "bundle_id": bundle_id,
            "created_ts_ms": created_ts_ms,
            "level": level,
            "window": {"from_ts_ms": window_from_ts_ms, "to_ts_ms": window_to_ts_ms},
            "focus": focus or {"incident_id": None, "module": None},
            "limits": {
                "max_total_bytes": limits.max_total_bytes,
                "max_file_bytes": limits.max_file_bytes,
                "max_files": limits.max_files,
            },
            "limits_hit": budget.limits_hit,
            "redaction": {
                "enabled": True,
                "mode": "strict",
                "pseudonymization": {"enabled": True, "method": "hmac-sha256", "salt_id": salt_id},
                "stats": dataclasses.asdict(red_stats),
            },
            "contributors": contributors,
        }

        # README.md
        findings = [
            f"Level: {level}",
            f"Window: {_iso(window_from_ts_ms)} → {_iso(window_to_ts_ms)}",
            f"Included dev log items: {len(dev_log_items)}",
        ]
        readme_lines = [
            "# Diagnostics Bundle (redacted)",
            "",
            "This bundle follows diagnostics_contract v0.1.",
            "",
            "## Scope",
            f"- Contract: {CONTRACT} {CONTRACT_VERSION}",
            f"- Bundle ID: {bundle_id}",
            f"- Created: {_iso(created_ts_ms)}",
            f"- Level: {level}",
            f"- Window: {_iso(window_from_ts_ms)} → {_iso(window_to_ts_ms)}",
            "",
            "## Quick summary (Top findings)",
        ]
        for f in findings[:5]:
            readme_lines.append(f"- {f}")
        readme_lines += [
            "",
            "## Privacy", 
            "- This bundle is sanitized/redacted (best-effort).",
            "- Tokens/PII should not be present; please preview before sharing.",
            "",
            "## Limits hit",
        ]
        if budget.limits_hit:
            for hit in budget.limits_hit:
                readme_lines.append(f"- {hit['kind']}: {hit['path']} ({hit['detail']})")
        else:
            readme_lines.append("- (none)")
        readme_lines.append("")
        write_text("README.md", "\n".join(readme_lines) + "\n")

        write_json("manifest.json", manifest)

        # Post-write heuristic scan: if we accidentally left something obvious, note it.
        # (We do not fail; operator preview is still required.)
        scan_hits: list[dict[str, Any]] = []
        for p in ["README.md", "manifest.json", f"modules/{module_name}/logs.txt"]:
            if p.endswith("logs.txt") and level == "minimal":
                continue
            try:
                data = zf.read(p).decode("utf-8", errors="replace")
            except Exception:
                continue
            hs = _best_effort_secret_scan(data)
            if hs:
                scan_hits.append({"path": p, "hits": hs})
        if scan_hits:
            budget.limits_hit.append({"kind": "secret_scan", "path": "(bundle)", "detail": _json_dumps(scan_hits)})

    return zbuf.getvalue(), manifest
