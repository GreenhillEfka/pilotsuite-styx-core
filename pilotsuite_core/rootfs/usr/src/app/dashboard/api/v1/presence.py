from __future__ import annotations

from copy import deepcopy

from flask import Blueprint, jsonify


presence_bp = Blueprint("presence_v1", __name__, url_prefix="/api/v1/presence")

_AWAY_STATES = {"", "0", "away", "disconnected", "false", "not_home", "not_present", "off", "unknown"}

_PRESENCE_SNAPSHOT = [
    {
        "person_id": "person.andreas",
        "name": "Andreas",
        "icon": "mdi:account-circle",
        "state": "home",
        "zone": "office",
        "since": "2026-04-08T03:55:00+00:00",
        "updated_at": "2026-04-08T04:18:00+00:00",
    },
    {
        "person_id": "person.mira",
        "name": "Mira",
        "icon": "mdi:account",
        "state": "home",
        "zone": "room_mira",
        "since": "2026-04-08T04:05:00+00:00",
        "updated_at": "2026-04-08T04:15:00+00:00",
    },
    {
        "person_id": "person.paul",
        "name": "Paul",
        "icon": "mdi:account",
        "state": "not_home",
        "zone": "",
        "since": "2026-04-08T02:10:00+00:00",
        "updated_at": "2026-04-08T04:10:00+00:00",
    },
]


def _is_home(person: dict[str, str]) -> bool:
    return person.get("state", "").strip().lower() not in _AWAY_STATES


def _household_status(persons_home: list[dict[str, str]], persons_away: list[dict[str, str]]) -> str:
    if not persons_home and not persons_away:
        return "unknown"
    if persons_home and not persons_away:
        return "home"
    if persons_away and not persons_home:
        return "away"
    return "partial"


@presence_bp.get("")
def get_presence_summary():
    persons_home = sorted(
        (deepcopy(person) for person in _PRESENCE_SNAPSHOT if _is_home(person)),
        key=lambda person: person["name"].casefold(),
    )
    persons_away = sorted(
        (deepcopy(person) for person in _PRESENCE_SNAPSHOT if not _is_home(person)),
        key=lambda person: person["name"].casefold(),
    )

    return jsonify(
        {
            "ok": True,
            "source": "static_presence_snapshot",
            "household_status": _household_status(persons_home, persons_away),
            "persons_home": persons_home,
            "persons_away": persons_away,
            "total_home": len(persons_home),
            "total_tracked": len(_PRESENCE_SNAPSHOT),
            "hold_active": {},
            "last_updated": max(person["updated_at"] for person in _PRESENCE_SNAPSHOT),
        }
    )
