from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import user_hints as module  # noqa: E402
from copilot_core.api.v1.models import HintData, HintStatus, HintType  # noqa: E402


class FakeUserHintsService:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.accepted: list[str] = []
        self.rejected: list[tuple[str, str | None]] = []
        self.add_counter = 0
        self._hints: dict[str, HintData] = {
            "hint-alpha": HintData(
                hint_id="hint-alpha",
                title="Licht mit Kaffee syncen",
                description="Schalte Licht mit der Kaffeemaschine",
                hint_type=HintType.SUGGESTION,
                status=HintStatus.ACTIVE,
                entity_ids=["switch.coffee", "light.kitchen"],
                confidence=0.8,
                metadata={"source": "seed"},
            ),
            "hint-beta": HintData(
                hint_id="hint-beta",
                title="Abendroutine",
                description="Rollladen und Licht abends gemeinsam schalten",
                hint_type=HintType.AUTOMATION,
                status=HintStatus.ACTIVE,
                entity_ids=["cover.living_room", "light.living_room"],
                confidence=0.9,
                metadata={"source": "seed"},
            ),
            "hint-gamma": HintData(
                hint_id="hint-gamma",
                title="Info-Hinweis",
                description="Nur zur Anzeige",
                hint_type=HintType.INFO,
                status=HintStatus.DISMISSED,
                entity_ids=[],
                confidence=0.2,
                metadata={"source": "seed"},
            ),
        }

    def _maybe_raise(self, name: str, message: str) -> None:
        if self.raise_on == name:
            raise RuntimeError(message)

    def get_hints(self, status: HintStatus | None = None):
        self._maybe_raise("get_hints", "list exploded")
        hints = list(self._hints.values())
        if status is not None:
            return [hint for hint in hints if hint.status == status]
        return [hint for hint in hints if hint.status == HintStatus.ACTIVE]

    async def add_hint(self, text: str, hint_type: HintType | None = None):
        self._maybe_raise("add_hint", "add exploded")
        self.add_counter += 1
        hint_id = f"hint-new-{self.add_counter}"
        hint = HintData(
            hint_id=hint_id,
            title=text[:80],
            description=text,
            hint_type=hint_type or HintType.SUGGESTION,
            status=HintStatus.ACTIVE,
            entity_ids=[],
            confidence=0.5,
            metadata={"source": "fake_add"},
        )
        self._hints[hint_id] = hint
        return hint

    async def get_hint_by_id(self, hint_id: str):
        self._maybe_raise("get_hint_by_id", "get exploded")
        return self._hints.get(hint_id)

    async def accept_suggestion(self, hint_id: str):
        self._maybe_raise("accept_suggestion", "accept exploded")
        hint = self._hints.get(hint_id)
        if hint is None:
            return False
        hint.status = HintStatus.DISMISSED
        hint.metadata["accepted"] = True
        self.accepted.append(hint_id)
        return True

    async def reject_suggestion(self, hint_id: str, reason: str | None = None):
        self._maybe_raise("reject_suggestion", "reject exploded")
        hint = self._hints.get(hint_id)
        if hint is None:
            return False
        hint.status = HintStatus.DISMISSED
        if reason is not None:
            hint.metadata["reject_reason"] = reason
        self.rejected.append((hint_id, reason))
        return True

    def get_suggestions(self):
        self._maybe_raise("get_suggestions", "suggestions exploded")
        return [
            hint
            for hint in self._hints.values()
            if hint.hint_type in (HintType.AUTOMATION, HintType.SUGGESTION)
            and hint.status == HintStatus.ACTIVE
        ]


def _build_client(monkeypatch, *, authorized: bool = True, service: FakeUserHintsService | None = None):
    monkeypatch.setattr(module, "_validate_token", lambda _request: authorized)
    module.init_hints_service(service or FakeUserHintsService())
    app = Flask(__name__)
    app.register_blueprint(module.user_hints_bp, url_prefix="/api/v1/hints")
    return app.test_client(), module.get_hints_service()


def test_user_hints_contract_covers_all_routes(monkeypatch) -> None:
    client, service = _build_client(monkeypatch)

    response = client.get("/api/v1/hints")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "hints": [
            {
                "id": "hint-alpha",
                "title": "Licht mit Kaffee syncen",
                "description": "Schalte Licht mit der Kaffeemaschine",
                "type": "suggestion",
                "status": "active",
                "entity_ids": ["switch.coffee", "light.kitchen"],
                "confidence": 0.8,
                "metadata": {"source": "seed"},
            },
            {
                "id": "hint-beta",
                "title": "Abendroutine",
                "description": "Rollladen und Licht abends gemeinsam schalten",
                "type": "automation",
                "status": "active",
                "entity_ids": ["cover.living_room", "light.living_room"],
                "confidence": 0.9,
                "metadata": {"source": "seed"},
            },
        ],
        "count": 2,
    }

    response = client.get("/api/v1/hints?status=dismissed")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "hints": [
            {
                "id": "hint-gamma",
                "title": "Info-Hinweis",
                "description": "Nur zur Anzeige",
                "type": "info",
                "status": "dismissed",
                "entity_ids": [],
                "confidence": 0.2,
                "metadata": {"source": "seed"},
            }
        ],
        "count": 1,
    }

    response = client.post("/api/v1/hints", json={"text": "Bitte morgens erinnern", "type": "warning"})
    assert response.status_code == 201
    created = response.get_json()
    assert created == {
        "ok": True,
        "hint": {
            "id": "hint-new-1",
            "title": "Bitte morgens erinnern",
            "description": "Bitte morgens erinnern",
            "type": "warning",
            "status": "active",
            "entity_ids": [],
            "confidence": 0.5,
            "metadata": {"source": "fake_add"},
        },
    }

    response = client.get("/api/v1/hints/hint-new-1")
    assert response.status_code == 200
    assert response.get_json() == created

    response = client.get("/api/v1/hints/suggestions")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "suggestions": [
            {
                "id": "hint-alpha",
                "antecedent": "Licht mit Kaffee syncen",
                "consequent": "Schalte Licht mit der Kaffeemaschine",
                "confidence": 0.8,
                "type": "suggestion",
                "entity_ids": ["switch.coffee", "light.kitchen"],
            },
            {
                "id": "hint-beta",
                "antecedent": "Abendroutine",
                "consequent": "Rollladen und Licht abends gemeinsam schalten",
                "confidence": 0.9,
                "type": "automation",
                "entity_ids": ["cover.living_room", "light.living_room"],
            },
        ],
        "count": 2,
    }

    response = client.post("/api/v1/hints/hint-alpha/accept")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "message": "Suggestion accepted and automation created",
        "hint_id": "hint-alpha",
    }
    assert service.accepted == ["hint-alpha"]

    response = client.post("/api/v1/hints/hint-beta/reject", json={"reason": "Nicht jetzt"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "message": "Suggestion rejected",
        "hint_id": "hint-beta",
    }
    assert service.rejected == [("hint-beta", "Nicht jetzt")]

    response = client.get("/api/v1/hints/types")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "types": [
            {"value": "automation", "name": "AUTOMATION"},
            {"value": "suggestion", "name": "SUGGESTION"},
            {"value": "warning", "name": "WARNING"},
            {"value": "info", "name": "INFO"},
        ],
    }


def test_user_hints_contract_hardens_validation_not_found_and_runtime_errors(monkeypatch) -> None:
    service = FakeUserHintsService()
    client, _ = _build_client(monkeypatch, service=service)

    response = client.get("/api/v1/hints?status=broken")
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid status: broken",
        "valid_statuses": ["pending", "active", "dismissed", "expired"],
    }

    response = client.post("/api/v1/hints")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post("/api/v1/hints", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post("/api/v1/hints", json={"text": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "text must be a string"}

    response = client.post("/api/v1/hints", json={"text": "   "})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'text' field"}

    response = client.post("/api/v1/hints", json={"text": "Hallo", "type": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "type must be a string"}

    response = client.post("/api/v1/hints", json={"text": "Hallo", "type": "broken"})
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid type: broken",
        "valid_types": ["automation", "suggestion", "warning", "info"],
    }

    response = client.get("/api/v1/hints/missing")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Hint not found: missing"}

    response = client.post("/api/v1/hints/missing/accept")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Hint not found: missing"}

    response = client.post("/api/v1/hints/hint-alpha/reject", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post("/api/v1/hints/hint-alpha/reject", json={"reason": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "reason must be a string"}

    response = client.post("/api/v1/hints/missing/reject", json={"reason": "n/a"})
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Hint not found: missing"}

    service.raise_on = "get_hints"
    response = client.get("/api/v1/hints")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "list exploded"}

    service.raise_on = "add_hint"
    response = client.post("/api/v1/hints", json={"text": "Hallo"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "add exploded"}

    service.raise_on = "get_hint_by_id"
    response = client.get("/api/v1/hints/hint-alpha")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "get exploded"}

    service.raise_on = "accept_suggestion"
    response = client.post("/api/v1/hints/hint-alpha/accept")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "accept exploded"}

    service.raise_on = "reject_suggestion"
    response = client.post("/api/v1/hints/hint-alpha/reject", json={"reason": "later"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "reject exploded"}

    service.raise_on = "get_suggestions"
    response = client.get("/api/v1/hints/suggestions")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "suggestions exploded"}


def test_user_hints_contract_requires_authentication(monkeypatch) -> None:
    client, _ = _build_client(monkeypatch, authorized=False)

    response = client.get("/api/v1/hints")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
