# Migrated from pilotsuite-styx-ha (privacy.py)
"""PII Redaction — Centralized sanitization/redaction utilities.

Removes secrets/PII from free-form text:
- Email, phone, IP addresses, JWTs, Bearer tokens, URLs
- Configurable text clamping
- Object-level recursive sanitization

No HA dependencies — pure privacy logic.
"""

from __future__ import annotations

import dataclasses
import ipaddress
import re
from typing import Any


# Minimal pattern set per spec (best-effort).
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RE_PHONE = re.compile(r"\+?[0-9][0-9\s().-]{6,}")
_RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
)
_RE_BEARER = re.compile(r"(?i)(bearer\s+)(\S+)")
_RE_URL = re.compile(r"https?://[^\s]+")
# Long base64/hex-ish segments; heuristic for keys/tokens.
_RE_SECRETISH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_\-]{24,}(?![A-Za-z0-9])")


@dataclasses.dataclass
class RedactionStats:
    """Bounded counters only (no payload)."""

    redacted_email: int = 0
    redacted_phone: int = 0
    redacted_ip: int = 0
    redacted_url: int = 0
    redacted_secret: int = 0
    truncated: int = 0


def _clamp(s: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(s) <= max_chars:
        return s
    # keep room for suffix
    suffix = "…(truncated)…"
    keep = max(0, max_chars - len(suffix))
    return s[:keep] + suffix


def _mask_ipv4(ip_s: str) -> str:
    """Mask internal IPs; redact public IPs.

    - private IPv4: keep first 2 octets, mask rest => 192.168.x.x
    - otherwise: [REDACTED_IP]
    """

    try:
        ip = ipaddress.ip_address(ip_s)
    except ValueError:
        return "[REDACTED_IP]"

    if isinstance(ip, ipaddress.IPv4Address) and ip.is_private:
        parts = ip_s.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.x.x"
        return "[REDACTED_IP]"

    return "[REDACTED_IP]"


def sanitize_text(
    text: Any,
    *,
    stats: RedactionStats | None = None,
    max_chars: int = 500,
) -> str:
    """Sanitize free-form text.

    - Cast to string (safe default)
    - Strip/normalize whitespace
    - Redact common PII/secrets patterns
    - Clamp length

    Returns a string (possibly empty).
    """

    if text is None:
        return ""

    s = str(text)
    if not s:
        return ""

    # Normalize whitespace early.
    s = " ".join(s.strip().split())

    def _subn(regex: re.Pattern[str], repl: str, src: str, field: str) -> str:
        nonlocal stats
        if stats is None:
            return regex.sub(repl, src)
        out, n = regex.subn(repl, src)
        if n:
            setattr(stats, field, getattr(stats, field) + n)
        return out

    # URLs: always drop query/fragment; if token-ish in query/fragment => redact URL.
    def _url_repl(m: re.Match[str]) -> str:
        url = m.group(0)
        base = url.split("?", 1)[0].split("#", 1)[0]
        # token-ish heuristics: if query mentions secrets or contains long segments.
        if "?" in url or "#" in url:
            q = url.split("?", 1)[1] if "?" in url else ""
            low = q.lower()
            if any(k in low for k in ("token", "key", "auth", "password", "secret", "code")):
                return "[REDACTED_URL]"
        if _RE_SECRETISH.search(url):
            return "[REDACTED_URL]"
        return base

    if stats is None:
        s = _RE_URL.sub(_url_repl, s)
    else:
        # Count URL hits by using subn.
        s, n = _RE_URL.subn(_url_repl, s)
        stats.redacted_url += n

    s = _subn(_RE_BEARER, r"\1[REDACTED_SECRET]", s, "redacted_secret")
    s = _subn(_RE_JWT, "[REDACTED_SECRET]", s, "redacted_secret")
    s = _subn(_RE_SECRETISH, "[REDACTED_SECRET]", s, "redacted_secret")
    s = _subn(_RE_EMAIL, "[REDACTED_EMAIL]", s, "redacted_email")
    s = _subn(_RE_PHONE, "[REDACTED_PHONE]", s, "redacted_phone")

    # IPv4: custom replacement (mask internal, redact others).
    def _ip_repl(m: re.Match[str]) -> str:
        nonlocal stats
        if stats is not None:
            stats.redacted_ip += 1
        return _mask_ipv4(m.group(0))

    s = _RE_IPV4.sub(_ip_repl, s)

    out = _clamp(s, max_chars=max_chars)
    if stats is not None and out != s:
        stats.truncated += 1
    return out


def sanitize_path(path: Any, *, keep_basename: bool = True, max_chars: int = 120) -> str:
    """Sanitize filesystem paths for reports.

    By default keeps only the basename to avoid leaking local layout.
    """

    if path is None:
        return ""

    s = str(path).strip()
    if not s:
        return ""

    if keep_basename:
        # Avoid importing pathlib for runtime overhead; simple split.
        base = s.replace("\\", "/").rsplit("/", 1)[-1]
        s = f"…/{base}" if base and base != s else base

    return _clamp(sanitize_text(s, max_chars=max_chars), max_chars=max_chars)


def sanitize_obj(obj: Any, *, max_str_chars: int = 500) -> Any:
    """Best-effort sanitization for simple JSON-like structures.

    - strings sanitized
    - lists/dicts traversed with bounded recursion (depth=4)

    Intended for diagnostics and local reports; not a full schema validator.
    """

    def _walk(x: Any, depth: int) -> Any:
        if depth <= 0:
            return "[TRUNCATED_OBJECT]"
        if x is None or isinstance(x, (bool, int, float)):
            return x
        if isinstance(x, str):
            return sanitize_text(x, max_chars=max_str_chars)
        if isinstance(x, dict):
            out: dict[str, Any] = {}
            for k, v in list(x.items())[:200]:
                out[str(k)[:80]] = _walk(v, depth - 1)
            return out
        if isinstance(x, list):
            return [_walk(v, depth - 1) for v in x[:200]]
        return sanitize_text(str(x), max_chars=max_str_chars)

    return _walk(obj, 4)


def redaction_stats_dict(stats: RedactionStats | None) -> dict[str, int] | None:
    if stats is None:
        return None
    return dataclasses.asdict(stats)
