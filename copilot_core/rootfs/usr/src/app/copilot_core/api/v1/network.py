"""
Network API (Tier 0) — PilotSuite.

Baseline network diagnostics that work for every installation, without UniFi.

Endpoints:
  GET /api/v1/network
  GET /api/v1/network/health
"""

from __future__ import annotations

import os
import socket
import time
from typing import Any

import requests
from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

network_bp = Blueprint("network", __name__, url_prefix="/api/v1/network")


def _get_token() -> str:
    return (
        os.environ.get("SUPERVISOR_TOKEN", "").strip()
        or os.environ.get("HOME_ASSISTANT_TOKEN", "").strip()
        or os.environ.get("HA_TOKEN", "").strip()
    )


def _probe_ha(timeout: float = 4.0) -> dict[str, Any]:
    token = _get_token()
    if not token:
        return {"ok": False, "reason": "no_token"}

    headers = {"Authorization": f"Bearer {token}"}
    # Supervisor proxy is the most reliable from inside the add-on.
    candidates = [
        "http://supervisor/core/api/config",
        os.environ.get("HOME_ASSISTANT_URL", "").rstrip("/") + "/api/config" if os.environ.get("HOME_ASSISTANT_URL") else "",
    ]
    for url in [u for u in candidates if u]:
        try:
            t0 = time.perf_counter()
            resp = requests.get(url, headers=headers, timeout=timeout)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            if resp.ok:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                return {
                    "ok": True,
                    "url": url,
                    "latency_ms": latency_ms,
                    "ha_version": data.get("version", ""),
                    "location_name": data.get("location_name", ""),
                }
            return {"ok": False, "url": url, "latency_ms": latency_ms, "http": resp.status_code}
        except Exception:
            continue
    return {"ok": False, "reason": "unreachable"}


def _probe_dns(host: str = "home-assistant.io") -> dict[str, Any]:
    try:
        ip = socket.gethostbyname(host)
        return {"ok": True, "host": host, "ip": ip}
    except Exception as exc:
        return {"ok": False, "host": host, "error": str(exc)[:120]}


def _local_ip_hint() -> str:
    """Best-effort local IP hint without sending packets."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
        finally:
            s.close()
    except Exception:
        return ""


@network_bp.route("", methods=["GET"])
@require_token
def network_status():
    ha = _probe_ha()
    dns = _probe_dns()
    local_ip = _local_ip_hint()

    status = "healthy"
    if not ha.get("ok"):
        status = "degraded"
    if not dns.get("ok") and not ha.get("ok"):
        status = "unhealthy"

    return jsonify(
        {
            "ok": True,
            "status": status,
            "local_ip": local_ip,
            "checks": {
                "home_assistant": ha,
                "dns": dns,
            },
        }
    )


@network_bp.route("/health", methods=["GET"])
@require_token
def network_health():
    """Health-style summary for dashboard module status."""
    data = network_status().get_json(silent=True) or {}
    status = str(data.get("status") or "unknown")
    http = 200 if status == "healthy" else 206 if status == "degraded" else 503
    return jsonify({"status": status, "ok": status in {"healthy", "degraded"}, **(data.get("checks") or {})}), http
