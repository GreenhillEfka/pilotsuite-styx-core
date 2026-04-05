from __future__ import annotations

import importlib.util
import sys
import types
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
ZONE_EDITOR_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "zone_editor.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)


class FakeBlueprint:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def route(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


class FakeRequest:
    def __init__(self, *, args: dict[str, object] | None = None, payload=None, is_json: bool = True) -> None:
        self.args = args or {}
        self._payload = payload
        self.is_json = is_json
        self.headers: dict[str, str] = {}
        self.path = "/test"
        self.method = "GET"
        self.remote_addr = "127.0.0.1"

    def get_json(self, force: bool = False):  # noqa: ARG002 - Flask-compatible signature
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeG:
    pass


class FlaskStub(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("flask")
        self.Blueprint = FakeBlueprint
        self.request = FakeRequest()
        self.g = FakeG()

    @staticmethod
    def jsonify(payload):
        return payload

    @staticmethod
    def redirect(target):
        return {"redirect": target}

    @staticmethod
    def url_for(endpoint: str, **values):
        if not values:
            return endpoint
        return f"{endpoint}:{values}"


def _load_zone_editor(monkeypatch):
    flask_stub = FlaskStub()
    monkeypatch.setitem(sys.modules, "flask", flask_stub)

    module_name = f"zone_editor_contract_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, ZONE_EDITOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    security_module = sys.modules["copilot_core.api.security"]
    monkeypatch.setattr(security_module, "validate_token", lambda _request: True)
    return module


def _set_request(module, *, args: dict[str, object] | None = None, payload=None, is_json: bool = True) -> None:
    request = FakeRequest(args=args, payload=payload, is_json=is_json)
    request.method = "POST" if payload is not None else "GET"
    module.request = request

    security_module = sys.modules.get("copilot_core.api.security")
    if security_module is not None:
        setattr(security_module, "flask_request", request)


def _unwrap(response):
    if isinstance(response, tuple):
        return response
    return response, 200


def test_zone_editor_modern_list_and_overview_filter_contracts(monkeypatch) -> None:
    module = _load_zone_editor(monkeypatch)
    engine = MagicMock()
    engine.get_overview.return_value = SimpleNamespace(
        zones=[
            {"zone_id": "zone:living", "zone_type": "living", "enabled": True},
            {"zone_id": "zone:kitchen", "zone_type": "kitchen", "enabled": False},
        ],
        total_rooms=3,
        total_entities=11,
        modes={"active": 1, "idle": 1},
        unassigned_rooms=["room:spare"],
    )
    engine.get_zone.side_effect = lambda zone_id: {
        "zone:living": {"zone_id": "zone:living", "zone_type": "living", "name": "Wohnbereich"},
        "zone:kitchen": {"zone_id": "zone:kitchen", "zone_type": "kitchen", "name": "Küche"},
    }[zone_id]
    monkeypatch.setattr(module, "get_zone_engine", lambda: engine)

    _set_request(module, args={"zone_type": "living"}, is_json=False)
    body, status = _unwrap(module.list_zones())

    assert status == 200
    assert body["ok"] is True
    assert body["total"] == 1
    assert [zone["zone_id"] for zone in body["zones"]] == ["zone:living"]

    _set_request(module, args={"zone_type": "living"}, is_json=False)
    body, status = _unwrap(module.get_overview())

    assert status == 200
    assert body["ok"] is True
    assert body["overview"]["total_zones"] == 1
    assert body["overview"]["active_zones"] == 1
    assert body["overview"]["zones"][0]["zone_id"] == "zone:living"

    _set_request(module, args={"zone_type": "not-a-zone"}, is_json=False)
    body, status = _unwrap(module.list_zones())

    assert status == 400
    assert body == {"ok": False, "error": "Invalid zone_type: not-a-zone"}


def test_zone_editor_modern_create_normalizes_enabled_modules(monkeypatch) -> None:
    module = _load_zone_editor(monkeypatch)
    engine = MagicMock()
    created_zone = {
        "zone_id": "zone:test",
        "name": "Test Zone",
        "zone_type": "kitchen",
        "enabled_modules": ["climate", "light"],
    }
    engine.get_zone.side_effect = [None, created_zone]
    monkeypatch.setattr(module, "get_zone_engine", lambda: engine)

    _set_request(
        module,
        payload={
            "zone_id": "zone:test",
            "name": "Test Zone",
            "zone_type": "kitchen",
            "rooms": ["room:kitchen"],
            "icon": "mdi:stove",
            "priority": 4,
            "enabled_modules": [" light ", "", "climate", "light"],
        },
    )
    body, status = _unwrap(module.create_zone())

    assert status == 201
    assert body["ok"] is True
    assert body["zone"]["zone_id"] == "zone:test"
    engine.create_zone.assert_called_once_with(
        "zone:test",
        "Test Zone",
        ["room:kitchen"],
        "mdi:stove",
        4,
        zone_type="kitchen",
        enabled_modules={"light", "climate"},
    )

    engine = MagicMock()
    engine.get_zone.return_value = None
    monkeypatch.setattr(module, "get_zone_engine", lambda: engine)
    _set_request(
        module,
        payload={
            "zone_id": "zone:test",
            "name": "Test Zone",
            "enabled_modules": "light",
        },
    )
    body, status = _unwrap(module.create_zone())

    assert status == 400
    assert body == {"ok": False, "error": "Invalid field: enabled_modules"}


def test_zone_editor_modern_update_syncs_rooms_and_modules(monkeypatch) -> None:
    module = _load_zone_editor(monkeypatch)
    engine = MagicMock()
    existing_zone = {
        "zone_id": "zone:test",
        "rooms": [
            {"room_id": "room:drop"},
            {"room_id": "room:keep"},
        ],
    }
    updated_zone = {
        "zone_id": "zone:test",
        "rooms": [
            {"room_id": "room:keep"},
            {"room_id": "room:add"},
        ],
        "enabled_modules": ["climate", "light"],
    }
    engine.get_zone.side_effect = [existing_zone, updated_zone]
    engine.set_zone_name.return_value = True
    engine.set_zone_icon.return_value = True
    engine.set_zone_type.return_value = True
    engine.set_zone_mode.return_value = True
    engine.set_zone_enabled_modules.return_value = True
    monkeypatch.setattr(module, "get_zone_engine", lambda: engine)

    _set_request(
        module,
        payload={
            "name": "Updated Zone",
            "icon": "mdi:sofa",
            "zone_type": "living",
            "mode": "active",
            "enabled": True,
            "priority": 7,
            "enabled_modules": ["light", "climate", "light"],
            "rooms": ["room:keep", " room:add ", ""],
        },
    )
    body, status = _unwrap(module.update_zone("zone:test"))

    assert status == 200
    assert body["ok"] is True
    engine.remove_room_from_zone.assert_called_once_with("zone:test", "room:drop")
    engine.add_room_to_zone.assert_called_once_with("zone:test", "room:add")
    engine.set_zone_enabled_modules.assert_called_once_with("zone:test", {"light", "climate"})
    engine.set_zone_priority.assert_called_once_with("zone:test", 7)

    engine = MagicMock()
    engine.get_zone.return_value = existing_zone
    monkeypatch.setattr(module, "get_zone_engine", lambda: engine)
    _set_request(module, payload={"enabled_modules": "light"})
    body, status = _unwrap(module.update_zone("zone:test"))

    assert status == 400
    assert body == {"ok": False, "error": "Invalid field: enabled_modules"}


def test_zone_editor_uninitialized_engine_returns_503_for_modern_and_legacy_surfaces(monkeypatch) -> None:
    module = _load_zone_editor(monkeypatch)

    def _raise_runtime_error():
        raise RuntimeError("Zone engine not initialized")

    monkeypatch.setattr(module, "get_zone_engine", _raise_runtime_error)

    _set_request(module, is_json=False)
    body, status = _unwrap(module.list_rooms())
    assert status == 503
    assert body == {"ok": False, "error": "Zone engine not initialized"}

    _set_request(module, payload={"zone_id": "zone:test", "name": "Test Zone"})
    body, status = _unwrap(module.create_zone())
    assert status == 503
    assert body == {"ok": False, "error": "Zone engine not initialized"}

    _set_request(module, is_json=False)
    body, status = _unwrap(module.list_zones_legacy())
    assert status == 503
    assert body == {"error": "Zone engine not initialized"}

    _set_request(module, payload={"zone_id": "zone:test", "name": "Test Zone"})
    body, status = _unwrap(module.create_zone_legacy())
    assert status == 503
    assert body == {"error": "Zone engine not initialized"}

    _set_request(module, is_json=False)
    body, status = _unwrap(module.delete_zone_legacy("zone:test"))
    assert status == 503
    assert body == {"error": "Zone engine not initialized"}


def test_zone_editor_legacy_create_list_and_update_contracts(monkeypatch) -> None:
    module = _load_zone_editor(monkeypatch)
    engine = MagicMock()
    created_zone = {
        "zone_id": "zone:test",
        "zone_type": "kitchen",
        "enabled_modules": ["climate", "light"],
    }
    engine.get_zone.side_effect = [None, created_zone]
    engine.get_overview.return_value = SimpleNamespace(zones=[{"zone_id": "zone:test"}])
    monkeypatch.setattr(module, "get_zone_engine", lambda: engine)

    _set_request(
        module,
        payload={
            "zone_id": "zone:test",
            "name": "Test Zone",
            "zone_type": "kitchen",
            "enabled_modules": ["light", "climate"],
            "priority": 4,
        },
    )
    body, status = _unwrap(module.create_zone_legacy())

    assert status == 200
    assert body["ok"] is True
    engine.create_zone.assert_called_once_with(
        "zone:test",
        "Test Zone",
        [],
        "mdi:home-floor-1",
        zone_type="kitchen",
        enabled_modules={"light", "climate"},
        priority=4,
    )

    engine.get_zone.side_effect = None
    engine.get_zone.return_value = created_zone

    _set_request(module, args={"zone_type": "kitchen"}, is_json=False)
    body, status = _unwrap(module.list_zones_legacy())

    assert status == 200
    assert body["count"] == 1
    assert body["zones"][0]["zone_id"] == "zone:test"
    assert "generated_at" in body

    engine = MagicMock()
    engine.get_zone.return_value = {"zone_id": "zone:test"}
    monkeypatch.setattr(module, "get_zone_engine", lambda: engine)
    _set_request(module, payload={"enabled_modules": "light"})
    body, status = _unwrap(module.update_zone_legacy("zone:test"))

    assert status == 400
    assert body == {"error": "Invalid field: enabled_modules"}

    _set_request(module, payload={"zone_id": "zone:test", "name": "Test Zone", "zone_type": "wrong"})
    engine = MagicMock()
    engine.get_zone.return_value = None
    monkeypatch.setattr(module, "get_zone_engine", lambda: engine)
    body, status = _unwrap(module.create_zone_legacy())

    assert status == 400
    assert body == {"error": "Invalid zone_type: wrong"}
