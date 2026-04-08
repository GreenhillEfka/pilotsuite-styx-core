"""Household / Altersgruppen-Modul -- Personenbezogene Alters- und Rollenverwaltung.

Stellt Haushaltsmitglieder-Profile mit altersabgeleiteten Eigenschaften bereit:
  - Altersgruppen (AgeGroup): infant, toddler, child, teen, adult
  - Empfohlene Bettzeit je Altersgruppe
  - Kind/Erwachsener-Unterscheidung (is_minor)

Beispiel-Familienkonfiguration::

    {"members": [
        {"person_entity_id": "person.andreas", "name": "Andreas",
         "birth_year": 1982, "role": "parent"},           # 44 Jahre, adult
        {"person_entity_id": "person.steffi", "name": "Steffi",
         "birth_year": 1986, "role": "parent"},            # 40 Jahre, adult
        {"person_entity_id": "person.mira", "name": "Mira",
         "birth_year": 2022, "role": "child"},             # 4 Jahre, toddler
        {"person_entity_id": "person.paul", "name": "Paul",
         "birth_year": 2024, "role": "child"},             # 2 Jahre, infant
    ]}
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class AgeGroup(str, Enum):
    """Altersgruppen-Klassifikation.

    Einteilung nach paediatrischen Richtwerten:
      INFANT  (0-2):   Saeugling / Kleinkind
      TODDLER (3-5):   Kindergartenkind
      CHILD   (6-11):  Schulkind
      TEEN    (12-17): Teenager
      ADULT   (18+):   Erwachsener
    """

    INFANT = "infant"      # 0-2
    TODDLER = "toddler"   # 3-5
    CHILD = "child"        # 6-11
    TEEN = "teen"          # 12-17
    ADULT = "adult"        # 18+


# Empfohlene Bettzeit (Stunde, 24h-Format) je Altersgruppe
_BEDTIME_HOURS: Dict[AgeGroup, int] = {
    AgeGroup.INFANT: 18,   # 18:00 Uhr
    AgeGroup.TODDLER: 19,  # 19:00 Uhr
    AgeGroup.CHILD: 20,    # 20:00 Uhr
    AgeGroup.TEEN: 21,     # 21:00 Uhr
    AgeGroup.ADULT: 23,    # 23:00 Uhr
}


def _age_group_from_age(age: int) -> AgeGroup:
    """Ordnet ein numerisches Alter der passenden Altersgruppe zu."""
    if age <= 2:
        return AgeGroup.INFANT
    if age <= 5:
        return AgeGroup.TODDLER
    if age <= 11:
        return AgeGroup.CHILD
    if age <= 17:
        return AgeGroup.TEEN
    return AgeGroup.ADULT


@dataclass
class HouseholdMember:
    """Ein einzelnes Haushaltsmitglied.

    Attributes:
        person_entity_id: HA ``person``-Entity-ID (z.B. "person.andreas").
        name: Anzeigename des Mitglieds.
        birth_year: Geburtsjahr -- daraus werden Alter und Altersgruppe abgeleitet.
        role: Rolle im Haushalt ("parent", "child", "member").
    """

    person_entity_id: str
    name: str
    birth_year: int
    role: str = "member"  # z.B. "parent", "child", "member"

    @property
    def age(self) -> int:
        """Aktuelles Alter (vereinfacht: aktuelles Jahr minus Geburtsjahr)."""
        return date.today().year - self.birth_year

    @property
    def age_group(self) -> AgeGroup:
        """Altersgruppe basierend auf dem aktuellen Alter."""
        return _age_group_from_age(self.age)

    @property
    def is_minor(self) -> bool:
        """True wenn die Person minderjaehrig ist (Alter < 18)."""
        return self.age < 18

    @property
    def suggested_bedtime_hour(self) -> int:
        """Empfohlene Bettzeit-Stunde (24h) basierend auf der Altersgruppe."""
        return _BEDTIME_HOURS.get(self.age_group, 23)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "person_entity_id": self.person_entity_id,
            "name": self.name,
            "birth_year": self.birth_year,
            "role": self.role,
            "age": self.age,
            "age_group": self.age_group.value,
            "is_minor": self.is_minor,
            "suggested_bedtime_hour": self.suggested_bedtime_hour,
        }


class HouseholdProfile:
    """Haushaltsprofil mit Abfragehelfern.

    Verwaltet eine Liste von HouseholdMember-Instanzen und bietet
    Methoden zur Abfrage von Anwesenheit, Altersgruppen, Bettzeiten
    und der Zusammenfassung fuer den Evaluierungskontext.
    """

    def __init__(self, members: List[HouseholdMember] | None = None) -> None:
        self._members: List[HouseholdMember] = members or []

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> HouseholdProfile:
        """Erstellt ein HouseholdProfile aus einem Konfigurations-Dict.

        Erwartetes Format::

            {"members": [
                {"person_entity_id": "person.andreas", "name": "Andreas",
                 "birth_year": 1982, "role": "parent"},
                {"person_entity_id": "person.steffi", "name": "Steffi",
                 "birth_year": 1986, "role": "parent"},
                {"person_entity_id": "person.mira", "name": "Mira",
                 "birth_year": 2022, "role": "child"},
                {"person_entity_id": "person.paul", "name": "Paul",
                 "birth_year": 2024, "role": "child"},
            ]}

        Ungueltige Eintraege werden uebersprungen und geloggt.
        """
        members: List[HouseholdMember] = []
        for m in config.get("members", []):
            if not isinstance(m, dict):
                continue
            try:
                members.append(HouseholdMember(
                    person_entity_id=m["person_entity_id"],
                    name=m["name"],
                    birth_year=int(m["birth_year"]),
                    role=m.get("role", "member"),
                ))
            except (KeyError, ValueError, TypeError) as exc:
                _LOGGER.warning("Skipping invalid household member %s: %s", m, exc)

        profile = cls(members)
        _LOGGER.info("HouseholdProfile: %d members loaded", len(members))
        return profile

    # ------------------------------------------------------------------
    # Abfragehelfer
    # ------------------------------------------------------------------

    @property
    def members(self) -> List[HouseholdMember]:
        """Gibt eine Kopie der Mitgliederliste zurueck."""
        return list(self._members)

    def get_member(self, person_entity_id: str) -> Optional[HouseholdMember]:
        """Sucht ein Mitglied anhand der person-Entity-ID."""
        for m in self._members:
            if m.person_entity_id == person_entity_id:
                return m
        return None

    def get_adults(self) -> List[HouseholdMember]:
        """Gibt alle erwachsenen Haushaltsmitglieder zurueck (Alter >= 18)."""
        return [m for m in self._members if not m.is_minor]

    def get_children(self) -> List[HouseholdMember]:
        """Gibt alle minderjaehrigen Haushaltsmitglieder zurueck (Alter < 18)."""
        return [m for m in self._members if m.is_minor]

    def is_child_present(self, present_entity_ids: List[str]) -> bool:
        """Prueft, ob mindestens ein Kind unter den anwesenden Personen ist."""
        for m in self._members:
            if m.is_minor and m.person_entity_id in present_entity_ids:
                return True
        return False

    def is_only_children_home(self, present_entity_ids: List[str]) -> bool:
        """True wenn mindestens ein Kind zuhause ist, aber KEIN Erwachsener."""
        children_home = []
        adults_home = []
        for m in self._members:
            if m.person_entity_id in present_entity_ids:
                if m.is_minor:
                    children_home.append(m)
                else:
                    adults_home.append(m)
        return len(children_home) > 0 and len(adults_home) == 0

    def earliest_bedtime(self, present_entity_ids: List[str] | None = None) -> int:
        """Gibt die frueheste empfohlene Bettzeit-Stunde der anwesenden Mitglieder zurueck."""
        members = self._members
        if present_entity_ids is not None:
            members = [
                m for m in members if m.person_entity_id in present_entity_ids
            ]
        if not members:
            return 23
        return min(m.suggested_bedtime_hour for m in members)

    def presence_summary(self, present_entity_ids: List[str]) -> Dict[str, Any]:
        """Erstellt eine Anwesenheitszusammenfassung fuer den Evaluierungskontext.

        Gibt ein Dict mit Schluesseln zurueck: total_home, adults_home,
        children_home, only_children_home, earliest_bedtime_hour.
        """
        adults_home = []
        children_home = []
        for m in self._members:
            if m.person_entity_id in present_entity_ids:
                entry = {"name": m.name, "age": m.age, "age_group": m.age_group.value}
                if m.is_minor:
                    children_home.append(entry)
                else:
                    adults_home.append(entry)

        return {
            "total_home": len(adults_home) + len(children_home),
            "adults_home": adults_home,
            "children_home": children_home,
            "only_children_home": len(children_home) > 0 and len(adults_home) == 0,
            "earliest_bedtime_hour": self.earliest_bedtime(present_entity_ids),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "members": [m.to_dict() for m in self._members],
            "adults": len(self.get_adults()),
            "children": len(self.get_children()),
        }
