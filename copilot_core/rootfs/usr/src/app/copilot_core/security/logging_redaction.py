"""Centralized log redaction helpers for URL/header/payload logging.

The helpers here define a consistent policy for redacting likely secrets from
log messages and metadata. They intentionally keep context (e.g. keys, path,
endpoint) but replace secret-bearing values with a stable placeholder.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_REDACTION_PLACEHOLDER = "[REDACTED]"

# Heuristics for header and dict keys that are commonly secret-bearing.
_SENSITIVE_KEYWORDS = (
    "authorization",
    "authtoken",
    "xauthtoken",
    "apikey",
    "apiapikey",
    "apitoken",
    "accesskey",
    "accesskeyid",
    "access_token",
    "accesstoken",
    "secret",
    "password",
    "signature",
    "bearer",
    "session",
    "cookie",
)

# Regex for common textual auth/token artifacts.
_AUTH_TEXT_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(?:Bearer\s+)?([\w-_.~+/]+=*)"),
    re.compile(r"(?i)(x[-_]?api[-_]?key\s*[:=]\s*)([\w-_.~+/]+=*)"),
    re.compile(r"(?i)(x[-_]?auth[-_]?token\s*[:=]\s*)([\w-_.~+/]+=*)"),
)


def _normalize_key(key: str) -> str:
    """Normalize dict key/header names for keyword checks."""
    if key is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def is_sensitive_key(key: str) -> bool:
    """Return True when a key appears to carry a secret-like value."""
    normalized = _normalize_key(key)
    if not normalized:
        return False
    return any(keyword in normalized for keyword in _SENSITIVE_KEYWORDS)


def _redact_secret_token(value: str) -> str:
    """Replace explicit secrets in plain text values."""
    if not isinstance(value, str):
        return value

    redacted = value
    for pattern in _AUTH_TEXT_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}{_REDACTION_PLACEHOLDER}", redacted)
    return redacted


def _sanitize_netloc(netloc: str) -> str:
    """Redact credentials embedded in URL netloc."""
    if "@" not in netloc:
        return netloc
    host = netloc.rsplit("@", 1)[1]
    return f"***@{host}"


def sanitize_url(url: str) -> str:
    """Sanitize URL-like strings by redacting sensitive query values and credentials.

    Non-parseable/partial strings are still best-effort sanitized for query-like
    fragments with sensitive keys.
    """
    if not isinstance(url, str):
        return _REDACTION_PLACEHOLDER

    try:
        parsed = urlsplit(url)

        # query-like fragment in any string (e.g. bare `... ?token=...`).
        if not parsed.scheme and not parsed.netloc and "?" in url:
            base, query = url.split("?", 1)
            sanitized_query = _sanitize_query_params(query)
            return f"{base}?{sanitized_query}"

        # Full URL-like form
        query = parsed.query
        if query:
            query = _sanitize_query_params(query)
        fragment = _sanitize_query_params(parsed.fragment)
        return urlunsplit((
            parsed.scheme,
            _sanitize_netloc(parsed.netloc),
            parsed.path,
            query,
            fragment,
        ))
    except Exception:
        return _sanitize_query_params(url)


def _sanitize_query_params(query: str) -> str:
    """Redact secret values from a query-string fragment."""
    if not query:
        return query

    pairs = parse_qsl(query, keep_blank_values=True)
    redacted_pairs: list[tuple[str, str]] = []

    for key, value in pairs:
        if is_sensitive_key(key):
            redacted_pairs.append((key, _REDACTION_PLACEHOLDER))
        else:
            redacted_pairs.append((key, value))

    return urlencode(redacted_pairs, doseq=True)



def _looks_like_url(value: str) -> bool:
    """Heuristic: decide whether a string should be treated as a URL/query string."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v:
        return False
    if v.startswith("http://") or v.startswith("https://"):
        return True
    if "://" in v:
        return True
    # Query-string-like fragments, e.g. "token=...&foo=..."
    if "?" in v and "=" in v:
        return True
    return False


def sanitize_text(value: Any) -> str:
    """Apply redaction to arbitrary text values."""
    if value is None:
        return ""
    return _redact_secret_token(str(value))


def sanitize_payload(value: Any, *, _depth: int = 0) -> Any:
    """Recursively sanitize dict/list payloads while preserving structure."""
    if _depth > 8:
        return _REDACTION_PLACEHOLDER

    if isinstance(value, Mapping):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            if is_sensitive_key(str(key)):
                sanitized[str(key)] = _REDACTION_PLACEHOLDER
            else:
                sanitized[str(key)] = sanitize_payload(item, _depth=_depth + 1)
        return sanitized

    if isinstance(value, (list, tuple)):
        return [sanitize_payload(item, _depth=_depth + 1) for item in value]

    if isinstance(value, bytes):
        return sanitize_text(value.decode("utf-8", errors="replace"))

    if isinstance(value, str):
        return sanitize_url(value) if _looks_like_url(value) else sanitize_text(value)

    return sanitize_text(value)


def sanitize_headers(headers: Mapping[str, Any]) -> Dict[str, Any]:
    """Sanitize headers-like mappings used for logging."""
    if headers is None:
        return {}

    sanitized: Dict[str, Any] = {}
    for key, value in headers.items():
        if is_sensitive_key(str(key)):
            sanitized[str(key)] = _REDACTION_PLACEHOLDER
            continue
        sanitized[str(key)] = sanitize_payload(value)

    return sanitized


def sanitize_log_value(value: Any) -> Any:
    """General-purpose sanitizer used by logging helpers."""
    if isinstance(value, str):
        return sanitize_url(value) if _looks_like_url(value) else sanitize_text(value)
    if isinstance(value, Mapping) or isinstance(value, (list, tuple)):
        return sanitize_payload(value)
    return value


def as_log_text(value: Any) -> str:
    """Serialize values for logs with redaction applied."""
    sanitized = sanitize_log_value(value)
    if isinstance(sanitized, (dict, list, tuple)):
        return json.dumps(sanitized, sort_keys=True)
    return sanitize_text(sanitized)
