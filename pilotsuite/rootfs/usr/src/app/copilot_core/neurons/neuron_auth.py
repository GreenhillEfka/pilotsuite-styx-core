"""Neuron Capability & Auth Contract — Slice 135.

Definiert die Auth/Permission-Semantik für Neuron-level Zugriffe.
Geltungsbereich: Core-API Endpoints die Neuron-State lesen/schreiben.

Konsens-Basis: Lead-Entscheidung 2026-04-06 21:32 (Orakel → PilotClaw)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

_LOGGER = logging.getLogger(__name__)


class NeuronCapability(str, Enum):
    """Kann geloggt werden pro Neuron."""
    READ = "neuron:read"          # Neuron-State lesen
    WRITE = "neuron:write"        # Neuron-State überschreiben
    OVERRIDE = "neuron:override"  # Context-Override (Admin)
    EXECUTE = "neuron:execute"    # Neuron aktiv auslösen
    DISABLE = "neuron:disable"    # Neuron deaktivieren


@dataclass
class NeuronPermission:
    """Feingranulare Permission für einzelne Neuronen."""
    neuron_id: str
    capabilities: Set[NeuronCapability]
    granted_by: str = "system"
    granted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "neuron_id": self.neuron_id,
            "capabilities": [c.value for c in self.capabilities],
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
        }


@dataclass
class RolePermissions:
    """Permission-Set pro Rolle."""
    role: str
    neuron_permissions: List[NeuronPermission] = field(default_factory=list)

    def has_capability(self, neuron_id: str, cap: NeuronCapability) -> bool:
        for np in self.neuron_permissions:
            if np.neuron_id == neuron_id:
                if cap in np.capabilities:
                    return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "permissions": [np.to_dict() for np in self.neuron_permissions],
        }


# ─── Rollen-Definitionen (Default) ──────────────────────────────────────────

ROLE_ADMIN = RolePermissions(
    role="admin",
    neuron_permissions=[
        NeuronPermission(neuron_id="*", capabilities={
            NeuronCapability.READ,
            NeuronCapability.WRITE,
            NeuronCapability.OVERRIDE,
            NeuronCapability.EXECUTE,
            NeuronCapability.DISABLE,
        }, granted_by="system"),
    ],
)

ROLE_USER = RolePermissions(
    role="user",
    neuron_permissions=[
        NeuronPermission(neuron_id="*", capabilities={
            NeuronCapability.READ,
        }, granted_by="system"),
        # User darf tertentu Neuronen auch schreiben
        NeuronPermission(neuron_id="presence_intent", capabilities={
            NeuronCapability.WRITE,
        }, granted_by="system"),
        NeuronPermission(neuron_id="ambient_need", capabilities={
            NeuronCapability.WRITE,
        }, granted_by="system"),
    ],
)

ROLE_MODULE = RolePermissions(
    role="module",
    neuron_permissions=[
        NeuronPermission(neuron_id="*", capabilities={
            NeuronCapability.READ,
            NeuronCapability.WRITE,
            NeuronCapability.EXECUTE,
        }, granted_by="system"),
    ],
)

ROLE_SYSTEM = RolePermissions(
    role="system",
    neuron_permissions=[
        NeuronPermission(neuron_id="*", capabilities={
            NeuronCapability.READ,
        }, granted_by="system"),
    ],
)

ROLE_PERMISSIONS_MAP: Dict[str, RolePermissions] = {
    "admin": ROLE_ADMIN,
    "user": ROLE_USER,
    "module": ROLE_MODULE,
    "system": ROLE_SYSTEM,
}


# ─── Auth-Engine ─────────────────────────────────────────────────────────────

def get_role_permissions(role: str) -> RolePermissions:
    return ROLE_PERMISSIONS_MAP.get(role, ROLE_SYSTEM)


def check_neuron_capability(
    role: str,
    neuron_id: str,
    capability: NeuronCapability,
) -> bool:
    """Prüft ob Rolle die Capability für ein Neuron hat."""
    rp = get_role_permissions(role)

    # Wildcard-Permission prüfen
    if rp.has_capability("*", capability):
        return True

    # Spezifische Permission
    return rp.has_capability(neuron_id, capability)


def require_neuron_capability(
    role: Optional[str],
    neuron_id: str,
    capability: NeuronCapability,
    raise_on_fail: bool = True,
) -> bool:
    """Decorator-compatible Check. Gibt True zurück oder wirft AuthError."""
    if role is None:
        if raise_on_fail:
            raise PermissionError(f"Keine Rolle angegeben — {capability.value} auf {neuron_id} verweigert")
        return False

    if not check_neuron_capability(role, neuron_id, capability):
        _LOGGER.warning(
            "Auth verweigert: role=%s capability=%s neuron_id=%s",
            role, capability.value, neuron_id,
        )
        if raise_on_fail:
            raise PermissionError(
                f"Role '{role}' hat keine Berechtigung: "
                f"{capability.value} auf Neuron '{neuron_id}'"
            )
        return False

    return True


# ─── Endpoint-Guards (für API-Layer) ────────────────────────────────────────

def guard_neuron_read(role: Optional[str], neuron_id: str) -> None:
    require_neuron_capability(role, neuron_id, NeuronCapability.READ)

def guard_neuron_write(role: Optional[str], neuron_id: str) -> None:
    require_neuron_capability(role, neuron_id, NeuronCapability.WRITE)

def guard_neuron_override(role: Optional[str], neuron_id: str) -> None:
    require_neuron_capability(role, neuron_id, NeuronCapability.OVERRIDE)

def guard_neuron_execute(role: Optional[str], neuron_id: str) -> None:
    require_neuron_capability(role, neuron_id, NeuronCapability.EXECUTE)

def guard_neuron_disable(role: Optional[str], neuron_id: str) -> None:
    require_neuron_capability(role, neuron_id, NeuronCapability.DISABLE)


# ─── Diagnose ────────────────────────────────────────────────────────────────

def get_auth_diagnosis(role: str, neuron_id: str) -> Dict[str, Any]:
    """Alle Capabilities einer Rolle für ein Neuron."""
    rp = get_role_permissions(role)
    caps = [c.value for c in NeuronCapability]
    result = {}
    for cap in caps:
        cap_enum = NeuronCapability(cap)
        result[cap] = rp.has_capability(neuron_id, cap_enum)
    return {"role": role, "neuron_id": neuron_id, "capabilities": result}
