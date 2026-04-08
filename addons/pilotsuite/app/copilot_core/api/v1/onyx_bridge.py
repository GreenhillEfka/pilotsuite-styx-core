"""Onyx bridge endpoints for deterministic Styx -> HA actions."""

from __future__ import annotations

import os
import re
from typing import Any

from flask import Blueprint, jsonify, request
import requests as http_requests

from copilot_core.api.security import require_token

onyx_bridge_bp = Blueprint("onyx_bridge", __name__, url_prefix="/api/v1/onyx")

_DEFAULT_ALLOWED_DOMAINS = frozenset(
    {
        "light",
        "switch",
        "scene",
        "fan",
        "cover",
        "climate",
        "media_player",
        "input_boolean",
        "script",
        "automation",
        "notify",
    }
)
_SERVICE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


def _ha_url() -> str:
    return os.environ.get("SUPERVISOR_API", "http://supervisor/core/api").rstrip("/")


def _ha_token() -> str:
    return os.environ.get("SUPERVISOR_TOKEN", "").strip()


def _auth_headers() -> dict[str, str]:
    token = _ha_token()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _allowed_domains() -> set[str]:
    raw = os.environ.get("ONYX_ALLOWED_SERVICE_DOMAINS", "").strip()
    if not raw:
        return set(_DEFAULT_ALLOWED_DOMAINS)
    if raw == "*":
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _normalize_entity_ids(value: Any) -> list[str]:
    items: list[str]
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple, set)):
        items = [str(v) for v in value]
    else:
        return []

    seen: set[str] = set()
    result: list[str] = []
    for raw in items:
        entity_id = str(raw or "").strip().lower()
        if not entity_id or not _ENTITY_ID_RE.fullmatch(entity_id):
            continue
        if entity_id in seen:
            continue
        seen.add(entity_id)
        result.append(entity_id)
    return result


@onyx_bridge_bp.route("/status", methods=["GET"])
@require_token
def onyx_status():
    """Health/status information for Onyx bridge wiring."""
    token = _ha_token()
    headers = _auth_headers()
    reachable = False
    error = ""

    if token:
        try:
            resp = http_requests.get(f"{_ha_url()}/config", headers=headers, timeout=5)
            reachable = resp.ok
            if not resp.ok:
                error = f"HA API returned {resp.status_code}"
        except Exception as exc:  # pragma: no cover - defensive fallback
            error = str(exc)

    allowed = sorted(_allowed_domains()) or ["*"]
    return jsonify(
        {
            "ok": True,
            "bridge": "onyx",
            "supervisor_api": _ha_url(),
            "has_supervisor_token": bool(token),
            "ha_reachable": reachable,
            "ha_error": error,
            "allowed_domains": allowed,
        }
    )


@onyx_bridge_bp.route("/ha/service-call", methods=["POST"])
@require_token
def onyx_ha_service_call():
    """Execute a controlled HA service call and optionally return readback state."""
    token = _ha_token()
    if not token:
        return jsonify({"ok": False, "error": "SUPERVISOR_TOKEN missing"}), 503

    body = request.get_json(silent=True) or {}
    domain = str(body.get("domain", "")).strip().lower()
    service = str(body.get("service", "")).strip().lower()
    if not _SERVICE_RE.fullmatch(domain):
        return jsonify({"ok": False, "error": "domain is required"}), 400
    if not _SERVICE_RE.fullmatch(service):
        return jsonify({"ok": False, "error": "service is required"}), 400

    allowed = _allowed_domains()
    if allowed and domain not in allowed:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"Domain '{domain}' is not allowed",
                    "allowed_domains": sorted(allowed),
                }
            ),
            403,
        )

    service_data = body.get("service_data")
    if service_data is None:
        service_data = {}
    if not isinstance(service_data, dict):
        return jsonify({"ok": False, "error": "service_data must be an object"}), 400

    explicit_entity_ids = _normalize_entity_ids(body.get("entity_id"))
    payload_entity_ids = _normalize_entity_ids(service_data.get("entity_id"))
    entity_ids = explicit_entity_ids or payload_entity_ids
    if entity_ids and "entity_id" not in service_data:
        service_data["entity_id"] = entity_ids[0] if len(entity_ids) == 1 else entity_ids

    target = body.get("target")
    if isinstance(target, dict):
        service_data["target"] = target

    headers = _auth_headers()
    try:
        resp = http_requests.post(
            f"{_ha_url()}/services/{domain}/{service}",
            json=service_data,
            headers=headers,
            timeout=10,
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": f"HA service call failed: {exc}"}), 502

    if not resp.ok:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "HA service call rejected",
                    "ha_status_code": resp.status_code,
                    "ha_response": (resp.text or "")[:400],
                }
            ),
            502,
        )

    readback_enabled = bool(body.get("readback", True))
    readback_ids = _normalize_entity_ids(body.get("readback_entity_ids")) or entity_ids
    states: list[dict[str, Any]] = []
    if readback_enabled and readback_ids:
        for entity_id in readback_ids[:25]:
            try:
                s_resp = http_requests.get(
                    f"{_ha_url()}/states/{entity_id}",
                    headers=headers,
                    timeout=5,
                )
                if not s_resp.ok:
                    continue
                state = s_resp.json()
                states.append(
                    {
                        "entity_id": state.get("entity_id", entity_id),
                        "state": state.get("state"),
                        "attributes": state.get("attributes", {}),
                        "last_changed": state.get("last_changed"),
                    }
                )
            except Exception:
                continue

    result_data: Any
    try:
        result_data = resp.json()
    except Exception:
        result_data = (resp.text or "")[:400]

    return jsonify(
        {
            "ok": True,
            "domain": domain,
            "service": service,
            "entity_ids": entity_ids,
            "ha_status_code": resp.status_code,
            "ha_result": result_data,
            "readback_states": states,
        }
    )
