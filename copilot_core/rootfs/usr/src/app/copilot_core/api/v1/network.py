"""
Network API (Tier 0) — PilotSuite.

Baseline network diagnostics that work for every installation, without UniFi.

Endpoints:
  GET /api/v1/network
  GET /api/v1/network/health
  GET /api/v1/network/devices
  GET /api/v1/network/interfaces
"""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Any

import requests
from flask import Blueprint, jsonify, request as flask_request
from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

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

    # Include device summary and interface info for T0 completeness
    device_info = _get_ha_device_count()
    interfaces = _get_network_interfaces()

    return jsonify(
        {
            "ok": True,
            "status": status,
            "local_ip": local_ip,
            "checks": {
                "home_assistant": ha,
                "dns": dns,
            },
            "devices": {
                "total": device_info.get("total", 0),
                "online": device_info.get("online", 0),
                "offline": device_info.get("offline", 0),
            },
            "interfaces": interfaces,
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


# ---- Device count from HA entities -----------------------------------------


def _get_ha_device_count(timeout: float = 5.0) -> dict[str, Any]:
    """Query HA for device_tracker entities to derive device counts."""
    token = _get_token()
    if not token:
        return {"ok": False, "reason": "no_token", "total": 0, "online": 0, "offline": 0}

    headers = {"Authorization": f"Bearer {token}"}
    candidates = [
        "http://supervisor/core/api/states",
        (os.environ.get("HOME_ASSISTANT_URL", "").rstrip("/") + "/api/states"
         if os.environ.get("HOME_ASSISTANT_URL") else ""),
    ]
    for url in [u for u in candidates if u]:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if not resp.ok:
                continue
            states = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else []
            if not isinstance(states, list):
                continue

            # Filter to device_tracker entities
            trackers = [
                s for s in states
                if isinstance(s, dict) and str(s.get("entity_id", "")).startswith("device_tracker.")
            ]
            online = sum(
                1 for t in trackers
                if str(t.get("state", "")).lower() in ("home", "on", "connected")
            )
            offline = len(trackers) - online

            return {
                "ok": True,
                "total": len(trackers),
                "online": online,
                "offline": offline,
                "devices": [
                    {
                        "entity_id": t.get("entity_id", ""),
                        "state": t.get("state", "unknown"),
                        "friendly_name": (t.get("attributes") or {}).get("friendly_name", ""),
                        "source_type": (t.get("attributes") or {}).get("source_type", ""),
                    }
                    for t in trackers[:100]  # cap to prevent oversized responses
                ],
            }
        except Exception:
            continue

    return {"ok": False, "reason": "unreachable", "total": 0, "online": 0, "offline": 0}


# ---- Network interfaces ---------------------------------------------------


def _get_network_interfaces() -> list[dict[str, Any]]:
    """Return basic network interface information.

    Uses /proc/net and socket information available inside the container.
    No external dependencies required.
    """
    interfaces: list[dict[str, Any]] = []
    try:
        import fcntl
        import struct
        import array

        # Enumerate interfaces from /proc/net/dev
        with open("/proc/net/dev", "r") as f:
            lines = f.readlines()[2:]  # skip header lines

        for line in lines:
            parts = line.strip().split(":")
            if len(parts) < 2:
                continue
            iface_name = parts[0].strip()
            if not iface_name:
                continue

            # Parse RX/TX bytes
            stats = parts[1].split()
            rx_bytes = int(stats[0]) if len(stats) > 0 else 0
            tx_bytes = int(stats[8]) if len(stats) > 8 else 0

            # Try to get IP via socket ioctl
            ip_addr = ""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                ip_addr = socket.inet_ntoa(
                    fcntl.ioctl(
                        sock.fileno(),
                        0x8915,  # SIOCGIFADDR
                        struct.pack("256s", iface_name[:15].encode("utf-8")),
                    )[20:24]
                )
                sock.close()
            except Exception:
                pass

            up = rx_bytes > 0 or tx_bytes > 0 or ip_addr != ""

            interfaces.append({
                "name": iface_name,
                "ip": ip_addr,
                "up": up,
                "rx_bytes": rx_bytes,
                "tx_bytes": tx_bytes,
            })
    except Exception as exc:
        _LOGGER.debug("Failed to enumerate network interfaces: %s", exc)

    return interfaces


# ---- Additional endpoints --------------------------------------------------


@network_bp.route("/devices", methods=["GET"])
@require_token
def network_devices():
    """Return device count and online/offline status from HA device_tracker entities."""
    device_info = _get_ha_device_count()
    return jsonify({
        "ok": device_info.get("ok", False),
        "total": device_info.get("total", 0),
        "online": device_info.get("online", 0),
        "offline": device_info.get("offline", 0),
        "devices": device_info.get("devices", []),
    })


@network_bp.route("/interfaces", methods=["GET"])
@require_token
def network_interfaces():
    """Return local network interface information."""
    interfaces = _get_network_interfaces()
    return jsonify({
        "ok": True,
        "count": len(interfaces),
        "interfaces": interfaces,
    })
