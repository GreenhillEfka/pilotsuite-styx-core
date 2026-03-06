"""Webhook destination policy (SSRF guardrails).

Dieses Modul liefert eine stdlib-only Default-Policy fuer ausgehende Webhooks.
Die Policy ist bewusst konservativ: ohne explizite Allow/Override werden private
und lokal-scope IP-Ranges sowie Cloud-Metadata-Endpoints geblockt.

Motivation:
- Webhook-Ziele sind Konfiguration und koennen (direkt oder indirekt) von
  nicht-vertrauenswuerdigen Inputs beeinflusst werden.
- Outbound SSRF kann u. a. Metadata-Endpoints (Cloud) oder lokale Dienste
  erreichen.

Die Policy ist als Callable kompatibel mit `WebhookPusher(destination_policy=...)`.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse
from typing import Callable, Iterable, List, Optional, Sequence, Set


def _split_csv(value: str) -> List[str]:
    return [part.strip().lower() for part in value.split(",") if part.strip()]


def _host_matches_patterns(host: str, patterns: Sequence[str]) -> bool:
    host = host.lower().rstrip(".")
    for pattern in patterns:
        pattern = pattern.lower().rstrip(".")
        if not pattern:
            continue
        if pattern.startswith("*."):
            suffix = pattern[2:]
            if suffix and (host == suffix or host.endswith("." + suffix)):
                return True
        elif host == pattern:
            return True
    return False


def _iter_resolved_ips(hostname: str) -> Iterable[ipaddress._BaseAddress]:
    """Resolve hostname to IPs.

    NOTE: This relies on the OS resolver and is expected to be mocked in tests.
    """
    infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    seen: Set[str] = set()
    for family, socktype, proto, canonname, sockaddr in infos:
        ip_str = sockaddr[0]
        if ip_str in seen:
            continue
        seen.add(ip_str)
        try:
            yield ipaddress.ip_address(ip_str)
        except ValueError:
            continue


# Cloud metadata endpoints / special addresses (deny even when allow_private=true)
_METADATA_IPS = [
    ipaddress.ip_network("169.254.169.254/32"),  # AWS/Azure/GCP (common)
    ipaddress.ip_network("169.254.170.2/32"),  # AWS ECS task metadata
    ipaddress.ip_network("100.100.100.200/32"),  # Alibaba Cloud metadata
    ipaddress.ip_network("168.63.129.16/32"),  # Azure IMDS / platform IP
]


_ALWAYS_BLOCKED_RANGES = [
    # Link-local (incl. metadata range), multicast/reserved/unspecified
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("ff00::/8"),
]


_PRIVATE_BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # unique local
]


def default_webhook_destination_policy_from_env() -> Callable[[str], bool]:
    """Build default destination policy from environment variables.

    Env vars:
    - PILOTSUITE_WEBHOOK_DESTINATION_ALLOW_PRIVATE (default: false)
    - PILOTSUITE_WEBHOOK_DESTINATION_RESOLVE_DNS (default: false)
    - PILOTSUITE_WEBHOOK_DESTINATION_ALLOWED_DOMAINS (csv, optional)
    - PILOTSUITE_WEBHOOK_DESTINATION_BLOCKED_DOMAINS (csv, optional)

    Notes:
    - DNS resolution is opt-in to avoid hard failures on startup in offline / CI contexts.
    - Even with ALLOW_PRIVATE=true we still deny link-local + known metadata IPs.
    """

    allow_private = os.environ.get("PILOTSUITE_WEBHOOK_DESTINATION_ALLOW_PRIVATE", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    resolve_dns = os.environ.get("PILOTSUITE_WEBHOOK_DESTINATION_RESOLVE_DNS", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    allowed_domains = _split_csv(os.environ.get("PILOTSUITE_WEBHOOK_DESTINATION_ALLOWED_DOMAINS", ""))
    blocked_domains = _split_csv(os.environ.get("PILOTSUITE_WEBHOOK_DESTINATION_BLOCKED_DOMAINS", ""))

    blocked_ranges = list(_ALWAYS_BLOCKED_RANGES)
    if not allow_private:
        blocked_ranges.extend(_PRIVATE_BLOCKED_RANGES)

    def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
        for meta in _METADATA_IPS:
            if ip in meta:
                return True
        for network in blocked_ranges:
            if ip in network:
                return True
        return False

    def policy(url: str) -> bool:
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname = hostname.lower().rstrip(".")

        if blocked_domains and _host_matches_patterns(hostname, blocked_domains):
            return False

        if allowed_domains and not _host_matches_patterns(hostname, allowed_domains):
            return False

        # Fast-path for literal IPs
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            ip = None

        if ip is not None:
            return not _is_blocked_ip(ip)

        # "localhost" is effectively loopback; treat it as such.
        if hostname == "localhost":
            if allow_private:
                return True
            return False

        if not resolve_dns:
            # Without resolution we can only enforce domain allow/blocklists.
            return True

        try:
            for resolved_ip in _iter_resolved_ips(hostname):
                if _is_blocked_ip(resolved_ip):
                    return False
        except Exception:
            # Fail closed: if we can't resolve, we don't send.
            return False

        return True

    return policy
