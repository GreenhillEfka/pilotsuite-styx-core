from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import entity_adoption as module  # noqa: E402


class FakeState:
    def __init__(self, zone_id: str) -> None:
        self.zone_id = zone_id

    def to_dict(self) -> dict[str, object]:
        return {
            "zone_id": self.zone_id,
            "adopted_entities": ["light.living_room", "sensor.temperature"],
            "room_ids": ["room:living"],
            "manual_assignment_count": 1,
        }


class FakeAssignment:
    def __init__(
        self,
        entity_id: str,
        zone_id: str,
        *,
        source_room_id: str | None = None,
        priority: str = "override",
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.entity_id = entity_id
        self.zone_id = zone_id
        self.source_room_id = source_room_id
        self.priority = priority
        self.metadata = metadata or {}

    @property
    def assignment_id(self) -> str:
        return f"{self.entity_id}:{self.zone_id}"

    def to_dict(self) -> dict[str, object]:
        return {
            "assignment_id": self.assignment_id,
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "source_room_id": self.source_room_id,
            "priority": self.priority,
            "metadata": self.metadata,
        }


class FakeAdoptionService:
    def __init__(self) -> None:
        self.zone_states = {"zone:living": FakeState("zone:living")}
        self.assignments = {"sensor.temp:zone:living": FakeAssignment("sensor.temp", "zone:living")}
        self._room_zone_map = {"room:living": "zone:living"}
        self.assignment_calls: list[dict[str, object]] = []
        self.removed_assignment_ids: list[str] = []
        self.room_zone_mappings: list[tuple[str, str]] = []
        self.entity_room_mappings: list[tuple[str, str]] = []
        self.refreshed_zone_ids: list[str] = []
        self.refresh_all_calls = 0

    async def get_zone_entities(self, zone_id: str) -> dict[str, object]:
        return {
            "zone_id": zone_id,
            "entities": ["light.living_room", "sensor.temp"],
            "manual_assignments": [self.assignments["sensor.temp:zone:living"].to_dict()],
        }

    def get_all_zone_states(self) -> dict[str, FakeState]:
        return self.zone_states

    async def assign_entity(
        self,
        *,
        entity_id: str,
        zone_id: str,
        source_room_id: str | None,
        priority,
        metadata: dict[str, object],
    ) -> FakeAssignment:
        self.assignment_calls.append(
            {
                "entity_id": entity_id,
                "zone_id": zone_id,
                "source_room_id": source_room_id,
                "priority": priority.name.lower(),
                "metadata": metadata,
            }
        )
        assignment = FakeAssignment(
            entity_id,
            zone_id,
            source_room_id=source_room_id,
            priority=priority.name.lower(),
            metadata=metadata,
        )
        self.assignments[assignment.assignment_id] = assignment
        return assignment

    async def remove_assignment(self, assignment_id: str) -> bool:
        if assignment_id not in self.assignments:
            return False
        self.removed_assignment_ids.append(assignment_id)
        del self.assignments[assignment_id]
        return True

    def get_stats(self) -> dict[str, object]:
        return {
            "zone_count": len(self.zone_states),
            "assignment_count": len(self.assignments),
            "manual_override_count": 1,
        }

    async def refresh_zone(self, zone_id: str) -> FakeState | None:
        self.refreshed_zone_ids.append(zone_id)
        return self.zone_states.get(zone_id)

    async def refresh_all_zones(self) -> dict[str, FakeState]:
        self.refresh_all_calls += 1
        return self.zone_states

    def set_room_zone_mapping(self, room_id: str, zone_id: str) -> None:
        self.room_zone_mappings.append((room_id, zone_id))
        self._room_zone_map[room_id] = zone_id

    def set_entity_room_mapping(self, entity_id: str, room_id: str) -> None:
        self.entity_room_mappings.append((entity_id, room_id))

    def get_all_assignments(self) -> list[FakeAssignment]:
        return list(self.assignments.values())

    def get_assignment(self, assignment_id: str) -> FakeAssignment | None:
        return self.assignments.get(assignment_id)


def _build_client(monkeypatch, service: FakeAdoptionService, *, authorized: bool = True):
    monkeypatch.setattr(module, "get_adoption_service", lambda: service)
    monkeypatch.setattr(module, "validate_token", lambda _request: authorized)
    app = Flask(__name__)
    app.register_blueprint(module.bp)
    return app.test_client()


def test_entity_adoption_contract_covers_zone_assignment_refresh_mapping_and_stats(monkeypatch) -> None:
    service = FakeAdoptionService()
    client = _build_client(monkeypatch, service)

    response = client.get("/api/v1/entity-adoption/zones/zone:living/entities")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "zone_id": "zone:living",
        "entities": ["light.living_room", "sensor.temp"],
        "manual_assignments": [service.assignments["sensor.temp:zone:living"].to_dict()],
    }

    response = client.get("/api/v1/entity-adoption/zones")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "zone_count": 1,
        "zones": {"zone:living": service.zone_states["zone:living"].to_dict()},
    }

    response = client.get("/api/v1/entity-adoption/stats")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "zone_count": 1,
        "assignment_count": 1,
        "manual_override_count": 1,
    }

    response = client.post(
        "/api/v1/entity-adoption/assign",
        json={
            "entity_id": "switch.coffee",
            "zone_id": "zone:living",
            "source_room_id": "room:living",
            "priority": "specific",
            "metadata": {"origin": "contract-test"},
        },
    )
    assert response.status_code == 201
    assert response.get_json() == {
        "status": "ok",
        "message": "Entity switch.coffee assigned to zone zone:living",
        "assignment": {
            "assignment_id": "switch.coffee:zone:living",
            "entity_id": "switch.coffee",
            "zone_id": "zone:living",
            "source_room_id": "room:living",
            "priority": "specific",
            "metadata": {"origin": "contract-test"},
        },
    }
    assert service.assignment_calls == [
        {
            "entity_id": "switch.coffee",
            "zone_id": "zone:living",
            "source_room_id": "room:living",
            "priority": "specific",
            "metadata": {"origin": "contract-test"},
        }
    ]

    response = client.delete("/api/v1/entity-adoption/assign/sensor.temp:zone:living")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "message": "Assignment sensor.temp:zone:living removed",
    }
    assert service.removed_assignment_ids == ["sensor.temp:zone:living"]

    response = client.post("/api/v1/entity-adoption/refresh/zone:living")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "message": "Zone zone:living refreshed",
        "state": service.zone_states["zone:living"].to_dict(),
    }

    response = client.post("/api/v1/entity-adoption/refresh")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "message": "Refreshed 1 zones",
        "zones": {"zone:living": service.zone_states["zone:living"].to_dict()},
    }
    assert service.refresh_all_calls == 1

    response = client.post(
        "/api/v1/entity-adoption/mapping/room-zone",
        json={"room_id": "room:kitchen", "zone_id": "zone:living"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "message": "Room room:kitchen mapped to zone zone:living",
    }
    assert service.room_zone_mappings == [("room:kitchen", "zone:living")]

    response = client.post(
        "/api/v1/entity-adoption/mapping/entity-room",
        json={"entity_id": "light.kitchen", "room_id": "room:living"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "message": "Entity light.kitchen mapped to room room:living",
    }
    assert service.entity_room_mappings == [("light.kitchen", "room:living")]
    assert service.refreshed_zone_ids == ["zone:living", "zone:living", "zone:living"]

    response = client.get("/api/v1/entity-adoption/assignments")
    assert response.status_code == 200
    assignments = response.get_json()
    assert assignments["status"] == "ok"
    assert assignments["count"] == 1
    assert assignments["assignments"] == [
        {
            "assignment_id": "switch.coffee:zone:living",
            "entity_id": "switch.coffee",
            "zone_id": "zone:living",
            "source_room_id": "room:living",
            "priority": "specific",
            "metadata": {"origin": "contract-test"},
        }
    ]

    response = client.get("/api/v1/entity-adoption/assignment/switch.coffee:zone:living")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "assignment": {
            "assignment_id": "switch.coffee:zone:living",
            "entity_id": "switch.coffee",
            "zone_id": "zone:living",
            "source_room_id": "room:living",
            "priority": "specific",
            "metadata": {"origin": "contract-test"},
        },
    }


def test_entity_adoption_contract_hardens_validation_and_not_found_paths(monkeypatch) -> None:
    service = FakeAdoptionService()
    client = _build_client(monkeypatch, service)

    response = client.post("/api/v1/entity-adoption/assign")
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "Request body required"}

    response = client.post("/api/v1/entity-adoption/assign", json=["bad"])
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "JSON body must be an object"}

    response = client.post(
        "/api/v1/entity-adoption/assign",
        json={"entity_id": "sensor.temp", "metadata": "bad"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "entity_id and zone_id are required"}

    response = client.post(
        "/api/v1/entity-adoption/assign",
        json={"entity_id": "sensor.temp", "zone_id": "zone:living", "metadata": "bad"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "metadata must be an object"}

    response = client.post("/api/v1/entity-adoption/mapping/room-zone", json={"room_id": "room:living"})
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "room_id and zone_id are required"}

    response = client.post(
        "/api/v1/entity-adoption/mapping/entity-room",
        json={"entity_id": "sensor.temp"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "entity_id and room_id are required"}

    response = client.delete("/api/v1/entity-adoption/assign/missing:zone")
    assert response.status_code == 404
    assert response.get_json() == {"status": "error", "message": "Assignment not found: missing:zone"}

    response = client.get("/api/v1/entity-adoption/assignment/missing:zone")
    assert response.status_code == 404
    assert response.get_json() == {"status": "error", "message": "Assignment not found: missing:zone"}


def test_entity_adoption_contract_requires_authentication(monkeypatch) -> None:
    service = FakeAdoptionService()
    client = _build_client(monkeypatch, service, authorized=False)

    response = client.get("/api/v1/entity-adoption/stats")
    assert response.status_code == 401
    assert response.get_json() == {
        "error": "unauthorized",
        "message": "Valid X-Auth-Token or Bearer token required",
    }


def test_entity_adoption_contract_returns_json_500_for_service_runtime_errors(monkeypatch) -> None:
    service = FakeAdoptionService()
    client = _build_client(monkeypatch, service)

    def explode_stats() -> None:
        raise RuntimeError("entity adoption exploded")

    async def explode_assign(**_kwargs):
        raise RuntimeError("entity adoption exploded")

    def explode_room_zone(_room_id: str, _zone_id: str) -> None:
        raise RuntimeError("entity adoption exploded")

    monkeypatch.setattr(service, "get_stats", explode_stats)
    response = client.get("/api/v1/entity-adoption/stats")
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "entity adoption exploded"}

    monkeypatch.setattr(service, "assign_entity", explode_assign)
    response = client.post(
        "/api/v1/entity-adoption/assign",
        json={"entity_id": "sensor.temp", "zone_id": "zone:living"},
    )
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "entity adoption exploded"}

    monkeypatch.setattr(service, "set_room_zone_mapping", explode_room_zone)
    response = client.post(
        "/api/v1/entity-adoption/mapping/room-zone",
        json={"room_id": "room:living", "zone_id": "zone:living"},
    )
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "entity adoption exploded"}
