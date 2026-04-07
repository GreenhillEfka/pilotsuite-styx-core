"""Tests fuer das Household/Altersgruppen-Modul.

Testet HouseholdMember, HouseholdProfile, AgeGroup-Zuordnung,
Bettzeit-Logik und Praesenz-Abfragen.

Referenz-Familie: Andreas (1982), Steffi (1986), Mira (2022), Paul (2024)
"""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import patch

from copilot_core.household import (
    AgeGroup,
    HouseholdMember,
    HouseholdProfile,
    _age_group_from_age,
    _BEDTIME_HOURS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAMILY_CONFIG = {
    "members": [
        {"person_entity_id": "person.andreas", "name": "Andreas", "birth_year": 1982, "role": "parent"},
        {"person_entity_id": "person.steffi", "name": "Steffi", "birth_year": 1986, "role": "parent"},
        {"person_entity_id": "person.mira", "name": "Mira", "birth_year": 2022, "role": "child"},
        {"person_entity_id": "person.paul", "name": "Paul", "birth_year": 2024, "role": "child"},
    ]
}


@pytest.fixture
def family() -> HouseholdProfile:
    return HouseholdProfile.from_config(FAMILY_CONFIG)


@pytest.fixture
def andreas() -> HouseholdMember:
    return HouseholdMember("person.andreas", "Andreas", 1982, "parent")


@pytest.fixture
def mira() -> HouseholdMember:
    return HouseholdMember("person.mira", "Mira", 2022, "child")


@pytest.fixture
def paul() -> HouseholdMember:
    return HouseholdMember("person.paul", "Paul", 2024, "child")


# ---------------------------------------------------------------------------
# AgeGroup Tests
# ---------------------------------------------------------------------------

class TestAgeGroup:

    def test_infant_range(self):
        assert _age_group_from_age(0) == AgeGroup.INFANT
        assert _age_group_from_age(1) == AgeGroup.INFANT
        assert _age_group_from_age(2) == AgeGroup.INFANT

    def test_toddler_range(self):
        assert _age_group_from_age(3) == AgeGroup.TODDLER
        assert _age_group_from_age(5) == AgeGroup.TODDLER

    def test_child_range(self):
        assert _age_group_from_age(6) == AgeGroup.CHILD
        assert _age_group_from_age(11) == AgeGroup.CHILD

    def test_teen_range(self):
        assert _age_group_from_age(12) == AgeGroup.TEEN
        assert _age_group_from_age(17) == AgeGroup.TEEN

    def test_adult_range(self):
        assert _age_group_from_age(18) == AgeGroup.ADULT
        assert _age_group_from_age(44) == AgeGroup.ADULT
        assert _age_group_from_age(99) == AgeGroup.ADULT

    def test_bedtime_hours_complete(self):
        """Jede Altersgruppe hat eine Bettzeit-Empfehlung."""
        for group in AgeGroup:
            assert group in _BEDTIME_HOURS


# ---------------------------------------------------------------------------
# HouseholdMember Tests
# ---------------------------------------------------------------------------

class TestHouseholdMember:

    def test_age_calculation(self, andreas):
        expected_age = date.today().year - 1982
        assert andreas.age == expected_age

    def test_adult_is_not_minor(self, andreas):
        assert not andreas.is_minor

    def test_child_is_minor(self, mira):
        assert mira.is_minor

    def test_infant_is_minor(self, paul):
        assert paul.is_minor

    def test_age_group_adult(self, andreas):
        assert andreas.age_group == AgeGroup.ADULT

    def test_age_group_toddler(self, mira):
        # Mira born 2022, in 2026 she is 4 -> TODDLER
        expected = _age_group_from_age(date.today().year - 2022)
        assert mira.age_group == expected

    def test_age_group_infant(self, paul):
        # Paul born 2024, in 2026 he is 2 -> INFANT
        expected = _age_group_from_age(date.today().year - 2024)
        assert paul.age_group == expected

    def test_bedtime_adult(self, andreas):
        assert andreas.suggested_bedtime_hour == 23

    def test_bedtime_toddler(self, mira):
        assert mira.suggested_bedtime_hour == _BEDTIME_HOURS[mira.age_group]

    def test_to_dict_keys(self, andreas):
        d = andreas.to_dict()
        assert set(d.keys()) == {
            "person_entity_id", "name", "birth_year", "role",
            "age", "age_group", "is_minor", "suggested_bedtime_hour",
        }

    def test_to_dict_values(self, andreas):
        d = andreas.to_dict()
        assert d["person_entity_id"] == "person.andreas"
        assert d["name"] == "Andreas"
        assert d["birth_year"] == 1982
        assert d["role"] == "parent"
        assert d["is_minor"] is False


# ---------------------------------------------------------------------------
# HouseholdProfile Tests
# ---------------------------------------------------------------------------

class TestHouseholdProfile:

    def test_from_config_member_count(self, family):
        assert len(family.members) == 4

    def test_from_config_empty(self):
        profile = HouseholdProfile.from_config({})
        assert len(profile.members) == 0

    def test_from_config_invalid_entries_skipped(self):
        config = {"members": [
            {"person_entity_id": "person.x", "name": "X", "birth_year": 1990},
            "not_a_dict",
            {"name": "Missing ID"},  # missing person_entity_id
        ]}
        profile = HouseholdProfile.from_config(config)
        assert len(profile.members) == 1

    def test_get_member_found(self, family):
        m = family.get_member("person.andreas")
        assert m is not None
        assert m.name == "Andreas"

    def test_get_member_not_found(self, family):
        assert family.get_member("person.nobody") is None

    def test_get_adults(self, family):
        adults = family.get_adults()
        assert len(adults) == 2
        names = {a.name for a in adults}
        assert names == {"Andreas", "Steffi"}

    def test_get_children(self, family):
        children = family.get_children()
        assert len(children) == 2
        names = {c.name for c in children}
        assert names == {"Mira", "Paul"}

    def test_is_child_present_true(self, family):
        assert family.is_child_present(["person.mira", "person.andreas"])

    def test_is_child_present_false(self, family):
        assert not family.is_child_present(["person.andreas", "person.steffi"])

    def test_is_only_children_home_true(self, family):
        assert family.is_only_children_home(["person.mira", "person.paul"])

    def test_is_only_children_home_false_with_adult(self, family):
        assert not family.is_only_children_home(
            ["person.mira", "person.paul", "person.andreas"]
        )

    def test_is_only_children_home_false_no_children(self, family):
        assert not family.is_only_children_home(["person.andreas"])

    def test_is_only_children_home_false_nobody(self, family):
        assert not family.is_only_children_home([])

    def test_earliest_bedtime_all_members(self, family):
        # Paul (infant) hat frueheste Bettzeit (18h)
        bt = family.earliest_bedtime()
        assert bt == _BEDTIME_HOURS[AgeGroup.INFANT]

    def test_earliest_bedtime_adults_only(self, family):
        bt = family.earliest_bedtime(["person.andreas", "person.steffi"])
        assert bt == 23

    def test_earliest_bedtime_no_members(self, family):
        bt = family.earliest_bedtime([])
        assert bt == 23  # Default

    def test_presence_summary(self, family):
        present = ["person.andreas", "person.mira"]
        summary = family.presence_summary(present)
        assert summary["total_home"] == 2
        assert len(summary["adults_home"]) == 1
        assert len(summary["children_home"]) == 1
        assert summary["only_children_home"] is False

    def test_presence_summary_only_children(self, family):
        present = ["person.mira", "person.paul"]
        summary = family.presence_summary(present)
        assert summary["only_children_home"] is True
        assert summary["total_home"] == 2

    def test_to_dict(self, family):
        d = family.to_dict()
        assert d["adults"] == 2
        assert d["children"] == 2
        assert len(d["members"]) == 4
