"""Multi-Home Manager for PilotSuite Hub (v6.0.0).

Manages multiple home instances for users with several properties.
Provides unified view, cross-home analytics, and home switching.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HomeInstance:
    """A single home in the multi-home setup."""

    home_id: str
    name: str
    address: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    timezone: str = "Europe/Berlin"
    core_url: str = ""
    token: str = ""
    status: str = "online"  # online, offline, syncing
    last_sync: str = ""
    device_count: int = 0
    energy_today_kwh: float = 0.0
    cost_today_eur: float = 0.0
    icon: str = "mdi:home"


@dataclass
class MultiHomeSummary:
    """Summary across all homes."""

    total_homes: int = 0
    online_homes: int = 0
    homes: list[dict[str, Any]] = field(default_factory=list)
    total_devices: int = 0
    total_energy_kwh: float = 0.0
    total_cost_eur: float = 0.0
    active_home_id: str = ""
    ok: bool = True


class MultiHomeManager:
    """Manages multiple home instances.

    Features:
    - Home registration and discovery
    - Cross-home aggregation (energy, cost, devices)
    - Active home switching
    - Sync status tracking
    """

    def __init__(self) -> None:
        self._homes: dict[str, HomeInstance] = {}
        self._active_home_id: str = ""

    def add_home(
        self,
        home_id: str,
        name: str,
        address: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
        core_url: str = "",
        token: str = "",
        icon: str = "mdi:home",
    ) -> bool:
        """Register a home instance."""
        if home_id in self._homes:
            return False

        self._homes[home_id] = HomeInstance(
            home_id=home_id,
            name=name,
            address=address,
            latitude=latitude,
            longitude=longitude,
            core_url=core_url,
            token=token,
            icon=icon,
            last_sync=datetime.now(timezone.utc).isoformat(),
        )

        if not self._active_home_id:
            self._active_home_id = home_id

        return True

    def remove_home(self, home_id: str) -> bool:
        """Remove a home instance."""
        if home_id not in self._homes:
            return False
        del self._homes[home_id]
        if self._active_home_id == home_id:
            self._active_home_id = next(iter(self._homes), "")
        return True

    def set_active_home(self, home_id: str) -> bool:
        """Switch active home."""
        if home_id not in self._homes:
            return False
        self._active_home_id = home_id
        return True

    def get_active_home(self) -> HomeInstance | None:
        """Get active home instance."""
        return self._homes.get(self._active_home_id)

    def update_home_status(
        self,
        home_id: str,
        status: str = "online",
        device_count: int | None = None,
        energy_kwh: float | None = None,
        cost_eur: float | None = None,
    ) -> bool:
        """Update a home's status and metrics."""
        home = self._homes.get(home_id)
        if not home:
            return False

        home.status = status
        home.last_sync = datetime.now(timezone.utc).isoformat()
        if device_count is not None:
            home.device_count = device_count
        if energy_kwh is not None:
            home.energy_today_kwh = energy_kwh
        if cost_eur is not None:
            home.cost_today_eur = cost_eur
        return True

    def get_home(self, home_id: str) -> dict[str, Any] | None:
        """Get home details."""
        home = self._homes.get(home_id)
        if not home:
            return None
        return {
            "home_id": home.home_id,
            "name": home.name,
            "address": home.address,
            "latitude": home.latitude,
            "longitude": home.longitude,
            "timezone": home.timezone,
            "core_url": home.core_url,
            "status": home.status,
            "last_sync": home.last_sync,
            "device_count": home.device_count,
            "energy_today_kwh": round(home.energy_today_kwh, 2),
            "cost_today_eur": round(home.cost_today_eur, 2),
            "icon": home.icon,
            "is_active": home.home_id == self._active_home_id,
        }

    def get_summary(self) -> MultiHomeSummary:
        """Get multi-home summary."""
        homes = []
        total_devices = 0
        total_energy = 0.0
        total_cost = 0.0
        online = 0

        for hid in self._homes:
            info = self.get_home(hid)
            if info:
                homes.append(info)
                total_devices += info.get("device_count", 0)
                total_energy += info.get("energy_today_kwh", 0)
                total_cost += info.get("cost_today_eur", 0)
                if info.get("status") == "online":
                    online += 1

        return MultiHomeSummary(
            total_homes=len(homes),
            online_homes=online,
            homes=homes,
            total_devices=total_devices,
            total_energy_kwh=round(total_energy, 2),
            total_cost_eur=round(total_cost, 2),
            active_home_id=self._active_home_id,
        )

    @property
    def home_count(self) -> int:
        """Number of registered homes."""
        return len(self._homes)

    @property
    def home_ids(self) -> list[str]:
        """List of registered home IDs."""
        return list(self._homes.keys())
