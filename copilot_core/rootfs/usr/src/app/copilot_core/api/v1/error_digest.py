"""Error Digest REST API Blueprint.

Prefix: /api/v1/errors
Aggregated error summary with categorization and repair suggestions.
"""

import logging
import time
from collections import Counter
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

_VALID_SEVERITIES = {"low", "medium", "high", "critical"}
_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

error_digest_bp = Blueprint("error_digest", __name__, url_prefix="/api/v1/errors")

_llm_provider: Optional[Any] = None


def init_error_digest_api(llm_provider=None) -> None:
    """Wire LLM provider into API blueprint."""
    global _llm_provider
    _llm_provider = llm_provider


def _get_dev_logs() -> list[dict]:
    """Read dev logs from the ring buffer cache."""
    try:
        from copilot_core.api.v1.dev import _DEV_LOG_CACHE, _ensure_dev_log_cache_loaded
        _ensure_dev_log_cache_loaded()
        return list(_DEV_LOG_CACHE)
    except Exception:
        return []


def _json_error(message: str, status: int):
    return jsonify({"ok": False, "error": message}), status


def _parse_hours(raw_value: Any) -> int:
    try:
        hours = int(raw_value)
    except (ValueError, TypeError) as exc:
        raise ValueError("hours must be a positive integer") from exc

    if hours <= 0:
        raise ValueError("hours must be a positive integer")
    return min(hours, 168)


def _require_json_object(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()


def _parse_log_timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            from datetime import datetime as _dt

            return _dt.fromisoformat(value).timestamp()
        except (ValueError, TypeError):
            return None

    return None


# ── Known error patterns and their repair suggestions ──────────────────

_REPAIR_PATTERNS = [
    {
        "pattern": "connection refused",
        "category": "connectivity",
        "severity": "high",
        "suggestion_de": "Verbindung abgelehnt. Pruefen Sie ob der Zieldienst laeuft und der Port korrekt ist.",
        "suggestion_en": "Connection refused. Check if the target service is running and port is correct.",
        "actions": ["restart_service", "check_port"],
    },
    {
        "pattern": "timeout",
        "category": "connectivity",
        "severity": "medium",
        "suggestion_de": "Zeitueberschreitung. Netzwerk pruefen oder Timeout erhoehen.",
        "suggestion_en": "Timeout. Check network or increase timeout value.",
        "actions": ["check_network", "increase_timeout"],
    },
    {
        "pattern": "entity not found",
        "category": "configuration",
        "severity": "medium",
        "suggestion_de": "Entity nicht gefunden. Pruefen Sie ob die Entity-ID korrekt ist und die Integration geladen ist.",
        "suggestion_en": "Entity not found. Verify entity ID and check if integration is loaded.",
        "actions": ["check_entity_id", "reload_integration"],
    },
    {
        "pattern": "permission denied",
        "category": "security",
        "severity": "high",
        "suggestion_de": "Zugriff verweigert. Berechtigungen und Token pruefen.",
        "suggestion_en": "Permission denied. Check permissions and auth token.",
        "actions": ["check_token", "check_permissions"],
    },
    {
        "pattern": "disk full",
        "category": "system",
        "severity": "critical",
        "suggestion_de": "Festplatte voll. Speicher freigeben (alte Backups, Logs, DB bereinigen).",
        "suggestion_en": "Disk full. Free up space (remove old backups, logs, clean DB).",
        "actions": ["clean_logs", "clean_backups", "prune_database"],
    },
    {
        "pattern": "out of memory",
        "category": "system",
        "severity": "critical",
        "suggestion_de": "Speicher erschoepft. Dienste mit hohem Speicherverbrauch pruefen oder Neustart.",
        "suggestion_en": "Out of memory. Check high-memory services or restart.",
        "actions": ["restart_service", "check_memory_usage"],
    },
    {
        "pattern": "database is locked",
        "category": "database",
        "severity": "high",
        "suggestion_de": "Datenbank gesperrt. Parallele Zugriffe pruefen, ggf. WAL-Modus aktivieren.",
        "suggestion_en": "Database locked. Check parallel access, enable WAL mode if needed.",
        "actions": ["enable_wal", "restart_service"],
    },
    {
        "pattern": "ssl",
        "category": "security",
        "severity": "medium",
        "suggestion_de": "SSL/TLS-Fehler. Zertifikat pruefen oder erneuern.",
        "suggestion_en": "SSL/TLS error. Check or renew certificate.",
        "actions": ["renew_certificate", "check_ssl_config"],
    },
    {
        "pattern": "automation failed",
        "category": "automation",
        "severity": "medium",
        "suggestion_de": "Automatisierung fehlgeschlagen. Trigger und Aktionen pruefen, Entity-Verfuegbarkeit checken.",
        "suggestion_en": "Automation failed. Check triggers, actions, and entity availability.",
        "actions": ["check_automation", "check_entities"],
    },
    {
        "pattern": "service not found",
        "category": "configuration",
        "severity": "medium",
        "suggestion_de": "Service nicht gefunden. Integration neu laden oder HA neu starten.",
        "suggestion_en": "Service not found. Reload integration or restart HA.",
        "actions": ["reload_integration", "restart_ha"],
    },
    {
        "pattern": "unavailable",
        "category": "device",
        "severity": "medium",
        "suggestion_de": "Geraet nicht erreichbar. Stromversorgung und Netzwerk pruefen.",
        "suggestion_en": "Device unavailable. Check power supply and network.",
        "actions": ["check_device_power", "check_network"],
    },
    {
        "pattern": "battery low",
        "category": "device",
        "severity": "low",
        "suggestion_de": "Batterie niedrig. Batterie austauschen.",
        "suggestion_en": "Battery low. Replace battery.",
        "actions": ["replace_battery"],
    },
]


def _match_repair_patterns(error_text: str) -> list[dict]:
    """Match error text against known repair patterns."""
    text_lower = error_text.lower()
    matches = []
    for pattern in _REPAIR_PATTERNS:
        if pattern["pattern"] in text_lower:
            matches.append({
                "category": pattern["category"],
                "severity": pattern["severity"],
                "suggestion": pattern["suggestion_de"],
                "actions": pattern["actions"],
            })
    return matches


def _categorize_error(error_text: str) -> str:
    """Categorize an error by content."""
    text_lower = error_text.lower()
    if any(w in text_lower for w in ["connect", "timeout", "refused", "network"]):
        return "connectivity"
    if any(w in text_lower for w in ["permission", "token", "auth", "ssl", "forbidden"]):
        return "security"
    if any(w in text_lower for w in ["entity", "service", "config", "not found"]):
        return "configuration"
    if any(w in text_lower for w in ["disk", "memory", "cpu", "load"]):
        return "system"
    if any(w in text_lower for w in ["database", "sqlite", "locked"]):
        return "database"
    if any(w in text_lower for w in ["automation", "trigger", "action"]):
        return "automation"
    if any(w in text_lower for w in ["device", "unavailable", "battery"]):
        return "device"
    return "other"


def _severity_from_level(level: str) -> str:
    """Map log level to severity."""
    level_upper = (level or "").upper()
    if level_upper == "CRITICAL":
        return "critical"
    if level_upper == "ERROR":
        return "high"
    if level_upper == "WARNING":
        return "medium"
    return "low"


@error_digest_bp.route("/digest", methods=["GET"])
@require_token
def error_digest():
    """Aggregated error summary with repair suggestions.

    Query params:
        hours (int): Look back N hours (default 24, max 168)
        category (str): Filter by category
        severity (str): Filter by min severity (low|medium|high|critical)
    """
    try:
        hours = _parse_hours(request.args.get("hours", 24))
        category_filter = request.args.get("category")
        severity_filter = request.args.get("severity")
        if severity_filter and severity_filter not in _VALID_SEVERITIES:
            raise ValueError(f"severity must be one of: {', '.join(sorted(_VALID_SEVERITIES))}")

        cutoff = time.time() - (hours * 3600)
        errors: list[dict] = []

        dev_logs = _get_dev_logs()
        if dev_logs:
            for entry in dev_logs:
                ts = _parse_log_timestamp(entry.get("timestamp") or entry.get("ts", 0))
                if ts is None or ts < cutoff:
                    continue

                level = str(entry.get("level", "ERROR") or "ERROR").upper()
                if level not in ("ERROR", "CRITICAL", "WARNING"):
                    continue

                msg = str(entry.get("message", "") or entry.get("msg", ""))
                source = str(entry.get("source", "") or entry.get("logger", ""))
                category = _categorize_error(msg)
                severity = _severity_from_level(level)
                repairs = _match_repair_patterns(msg)

                if category_filter and category != category_filter:
                    continue
                if severity_filter and _SEVERITY_ORDER.get(severity, 0) < _SEVERITY_ORDER[severity_filter]:
                    continue

                errors.append({
                    "timestamp": ts,
                    "level": level,
                    "message": msg[:500],
                    "source": source,
                    "category": category,
                    "severity": severity,
                    "repairs": repairs,
                })

        errors.sort(key=lambda e: e["timestamp"], reverse=True)
        category_counts = Counter(e["category"] for e in errors)
        severity_counts = Counter(e["severity"] for e in errors)

        return jsonify({
            "ok": True,
            "errors": errors[:100],
            "total": len(errors),
            "hours": hours,
            "summary": {
                "total_errors": len(errors),
                "by_category": dict(category_counts),
                "by_severity": dict(severity_counts),
                "categories": sorted(category_counts.keys()),
            },
        })
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        return _json_error(str(exc), 500)


@error_digest_bp.route("/digest/categories", methods=["GET"])
@require_token
def error_categories():
    """Available error categories and their descriptions."""
    return jsonify({
        "ok": True,
        "categories": {
            "connectivity": "Netzwerk- und Verbindungsfehler",
            "security": "Authentifizierung, Berechtigungen, SSL",
            "configuration": "Konfigurationsfehler, fehlende Entities/Services",
            "system": "Systemressourcen (CPU, RAM, Disk)",
            "database": "Datenbankfehler, Locking",
            "automation": "Automatisierungsfehler",
            "device": "Geraetefehler, Erreichbarkeit, Batterie",
            "other": "Sonstige Fehler",
        },
    })


@error_digest_bp.route("/repair-suggestions", methods=["POST"])
@require_token
def repair_suggestions():
    """Get repair suggestions for a specific error message.

    Request body: {"message": "the error message", "context": "optional additional context"}
    """
    try:
        data = _require_json_object(request.get_json(silent=True))
        message = _require_non_empty_string(data.get("message", ""), "message")
        context = _optional_string(data.get("context", ""), "context")

        repairs = _match_repair_patterns(message)

        if not repairs and _llm_provider is not None:
            try:
                prompt = (
                    f"Du bist ein Smart-Home-Experte. Analysiere diesen Fehler und schlage "
                    f"konkrete Reparaturschritte vor (auf Deutsch, max 3 Schritte):\n\n"
                    f"Fehler: {message[:300]}\n"
                )
                if context:
                    prompt += f"Kontext: {context[:200]}\n"

                response = _llm_provider.generate(prompt, max_tokens=300)
                if response and isinstance(response, str):
                    repairs.append({
                        "category": _categorize_error(message),
                        "severity": "medium",
                        "suggestion": response,
                        "actions": [],
                        "source": "llm",
                    })
            except Exception:
                _LOGGER.debug("LLM repair suggestion failed", exc_info=True)

        return jsonify({
            "ok": True,
            "message": message[:500],
            "repairs": repairs,
            "pattern_matches": len([r for r in repairs if r.get("source") != "llm"]),
        })
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        return _json_error(str(exc), 500)
