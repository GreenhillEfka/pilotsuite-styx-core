"""Praesenzmodul — Anwesenheitserkennung pro Zone (v1.0.0).

Kombiniert Bewegungsmelder, Device-Tracker, Tuersensoren und
WLAN-Erkennung fuer praezise Raumbelegung.

Features:
- Mehrere Praesenzquellen pro Zone (Bewegung, Device-Tracker, Tuer, WLAN)
- Personenerkennung und -zaehlung
- Belegungsdauer-Tracking
- Globale Anwesenheitsuebersicht
- LLM-Kontext fuer Sprachsteuerung
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PresenceSource:
    """Einzelne Praesenzquelle."""

    entity_id: str
    zone_id: str = ""
    source_type: str = "motion"  # motion | device_tracker | door | wifi
    is_present: bool = False
    person_name: str = ""
    last_change: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class ZonePresence:
    """Aggregierter Praesenz-Zustand einer Zone."""

    zone_id: str
    zone_name: str = ""
    is_occupied: bool = False
    person_count: int = 0
    persons: list[str] = field(default_factory=list)
    last_entered: datetime | None = None
    last_left: datetime | None = None
    occupied_since: datetime | None = None
    sources_active: int = 0
    sources_total: int = 0


@dataclass
class PraesenzDashboard:
    """Komplettes Praesenzmodul-Dashboard."""

    zones: list[dict[str, Any]] = field(default_factory=list)
    total_sources: int = 0
    persons_home: int = 0
    zones_occupied: int = 0
    zones_empty: int = 0


class PraesenzModuleEngine:
    """Praesenzmodul Engine — verwaltet Praesenzquellen pro Zone."""

    def __init__(self) -> None:
        self._sources: dict[str, PresenceSource] = {}
        self._zone_names: dict[str, str] = {}
        self._zone_occupied_since: dict[str, datetime | None] = {}
        self._zone_last_entered: dict[str, datetime | None] = {}
        self._zone_last_left: dict[str, datetime | None] = {}

    def register_source(
        self, entity_id: str, zone_id: str,
        source_type: str = "motion", person_name: str = "",
    ) -> PresenceSource:
        """Registriert eine Praesenzquelle."""
        source = PresenceSource(
            entity_id=entity_id, zone_id=zone_id,
            source_type=source_type, person_name=person_name,
        )
        self._sources[entity_id] = source
        logger.debug("Praesenzmodul: Quelle %s registriert in Zone %s (%s)", entity_id, zone_id, source_type)
        return source

    def remove_source(self, entity_id: str) -> bool:
        """Entfernt eine Praesenzquelle."""
        removed = self._sources.pop(entity_id, None)
        if removed:
            logger.debug("Praesenzmodul: Quelle %s entfernt", entity_id)
        return removed is not None

    def configure_zone(self, zone_id: str, zone_name: str = "") -> None:
        """Konfiguriert den Zonennamen."""
        if zone_name:
            self._zone_names[zone_id] = zone_name

    def update_presence(
        self, entity_id: str, is_present: bool, person_name: str = "",
    ) -> PresenceSource | None:
        """Aktualisiert den Praesenzstatus einer Quelle."""
        source = self._sources.get(entity_id)
        if source is None:
            return None

        was_present = source.is_present
        source.is_present = is_present
        source.last_change = datetime.now(tz=timezone.utc)
        if person_name:
            source.person_name = person_name

        zone_id = source.zone_id
        now = datetime.now(tz=timezone.utc)

        if is_present and not was_present:
            # Jemand ist eingetreten
            self._zone_last_entered[zone_id] = now
            if self._zone_occupied_since.get(zone_id) is None:
                self._zone_occupied_since[zone_id] = now
            logger.debug("Praesenzmodul: %s anwesend in Zone %s", entity_id, zone_id)
        elif not is_present and was_present:
            # Jemand hat verlassen
            self._zone_last_left[zone_id] = now
            # Pruefen ob Zone jetzt leer ist
            zone_sources = [s for s in self._sources.values() if s.zone_id == zone_id and s.is_present]
            if not zone_sources:
                self._zone_occupied_since[zone_id] = None
            logger.debug("Praesenzmodul: %s abwesend in Zone %s", entity_id, zone_id)

        return source

    def get_zone_presence(self, zone_id: str) -> ZonePresence:
        """Berechnet den Praesenz-Zustand einer Zone."""
        sources = [s for s in self._sources.values() if s.zone_id == zone_id]
        active = [s for s in sources if s.is_present]

        persons = list(set(
            s.person_name for s in active if s.person_name
        ))
        is_occupied = len(active) > 0

        return ZonePresence(
            zone_id=zone_id,
            zone_name=self._zone_names.get(zone_id, zone_id),
            is_occupied=is_occupied,
            person_count=len(persons),
            persons=sorted(persons),
            last_entered=self._zone_last_entered.get(zone_id),
            last_left=self._zone_last_left.get(zone_id),
            occupied_since=self._zone_occupied_since.get(zone_id),
            sources_active=len(active),
            sources_total=len(sources),
        )

    def get_all_persons_home(self) -> list[str]:
        """Gibt eine Liste aller anwesenden Personen zurueck (eindeutig)."""
        persons = set()
        for source in self._sources.values():
            if source.is_present and source.person_name:
                persons.add(source.person_name)
        return sorted(persons)

    def get_dashboard(self) -> PraesenzDashboard:
        """Erstellt das komplette Praesenzmodul-Dashboard."""
        zones_data: list[dict[str, Any]] = []
        zone_ids = set(s.zone_id for s in self._sources.values() if s.zone_id)
        zones_occupied = 0
        zones_empty = 0

        for zone_id in sorted(zone_ids):
            state = self.get_zone_presence(zone_id)
            if state.is_occupied:
                zones_occupied += 1
            else:
                zones_empty += 1
            zones_data.append({
                "zone_id": zone_id, "zone_name": state.zone_name,
                "is_occupied": state.is_occupied,
                "person_count": state.person_count,
                "persons": state.persons,
                "last_entered": state.last_entered.isoformat() if state.last_entered else None,
                "last_left": state.last_left.isoformat() if state.last_left else None,
                "occupied_since": state.occupied_since.isoformat() if state.occupied_since else None,
                "sources_active": state.sources_active,
                "sources_total": state.sources_total,
            })

        all_persons = self.get_all_persons_home()

        return PraesenzDashboard(
            zones=zones_data,
            total_sources=len(self._sources),
            persons_home=len(all_persons),
            zones_occupied=zones_occupied,
            zones_empty=zones_empty,
        )

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten."""
        d = self.get_dashboard()
        return {
            "total_sources": d.total_sources,
            "persons_home": d.persons_home,
            "persons": self.get_all_persons_home(),
            "zones_occupied": d.zones_occupied,
            "zones_empty": d.zones_empty,
            "zones": d.zones,
        }

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion."""
        d = self.get_dashboard()
        if d.total_sources == 0:
            return ""
        persons = self.get_all_persons_home()
        person_str = ", ".join(persons) if persons else "niemand"
        lines = [
            f"Praesenzmodul: {d.persons_home} Personen zuhause ({person_str}), "
            f"{d.zones_occupied} Zonen belegt, {d.zones_empty} leer"
        ]
        for z in d.zones:
            if z["is_occupied"]:
                who = ", ".join(z["persons"]) if z["persons"] else "unbekannt"
                lines.append(
                    f"  {z['zone_name']}: belegt ({who}), "
                    f"{z['sources_active']}/{z['sources_total']} Quellen aktiv"
                )
            else:
                lines.append(f"  {z['zone_name']}: leer")
        return "\n".join(lines)
