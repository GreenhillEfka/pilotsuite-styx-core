from __future__ import annotations

import importlib.util
import sys
import time
from datetime import datetime
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
MODULE_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "error_digest.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security as api_security_module  # noqa: E402

spec = importlib.util.spec_from_file_location("ps_error_digest_contract_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeLLMProvider:
    def __init__(self, response: str = "Pruefe Netzwerk und starte den betroffenen Dienst neu.") -> None:
        self.response = response
        self.calls: list[tuple[str, int]] = []
        self.raise_on_generate = False

    def generate(self, prompt: str, max_tokens: int = 300) -> str:
        self.calls.append((prompt, max_tokens))
        if self.raise_on_generate:
            raise RuntimeError("llm exploded")
        return self.response


class RaisingLogs:
    def __call__(self):
        raise RuntimeError("dev logs exploded")


def _build_client(monkeypatch, *, authorized: bool = True, llm_provider=None):
    monkeypatch.setattr(api_security_module, "validate_token", lambda _request: authorized)
    module.init_error_digest_api(llm_provider=llm_provider)

    app = Flask(__name__)
    app.register_blueprint(module.error_digest_bp)
    return app.test_client()


def test_error_digest_contract_covers_all_routes(monkeypatch) -> None:
    now = time.time()
    llm_provider = FakeLLMProvider(response="1. Netzwerk pruefen\n2. Dienst neu starten")
    client = _build_client(monkeypatch, llm_provider=llm_provider)

    mock_logs = [
        {
            "timestamp": now - 120,
            "level": "WARNING",
            "message": "Entity not found: light.kitchen",
            "source": "api",
        },
        {
            "timestamp": datetime.fromtimestamp(now - 60).isoformat(),
            "level": "ERROR",
            "message": "Connection refused to homeassistant.local:8123",
            "logger": "core",
        },
        {
            "timestamp": now - 60 * 60 * 30,
            "level": "ERROR",
            "message": "database is locked",
            "source": "db",
        },
        {
            "timestamp": now - 10,
            "level": "INFO",
            "message": "healthy",
            "source": "noise",
        },
    ]
    monkeypatch.setattr(module, "_get_dev_logs", lambda: mock_logs)

    response = client.get("/api/v1/errors/digest?hours=1")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "errors": [
            {
                "timestamp": float(mock_logs[1]["timestamp"] and datetime.fromisoformat(mock_logs[1]["timestamp"]).timestamp()),
                "level": "ERROR",
                "message": "Connection refused to homeassistant.local:8123",
                "source": "core",
                "category": "connectivity",
                "severity": "high",
                "repairs": [
                    {
                        "category": "connectivity",
                        "severity": "high",
                        "suggestion": "Verbindung abgelehnt. Pruefen Sie ob der Zieldienst laeuft und der Port korrekt ist.",
                        "actions": ["restart_service", "check_port"],
                    }
                ],
            },
            {
                "timestamp": float(now - 120),
                "level": "WARNING",
                "message": "Entity not found: light.kitchen",
                "source": "api",
                "category": "configuration",
                "severity": "medium",
                "repairs": [
                    {
                        "category": "configuration",
                        "severity": "medium",
                        "suggestion": "Entity nicht gefunden. Pruefen Sie ob die Entity-ID korrekt ist und die Integration geladen ist.",
                        "actions": ["check_entity_id", "reload_integration"],
                    }
                ],
            },
        ],
        "total": 2,
        "hours": 1,
        "summary": {
            "total_errors": 2,
            "by_category": {"connectivity": 1, "configuration": 1},
            "by_severity": {"high": 1, "medium": 1},
            "categories": ["configuration", "connectivity"],
        },
    }

    response = client.get("/api/v1/errors/digest/categories")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "categories": {
            "connectivity": "Netzwerk- und Verbindungsfehler",
            "security": "Authentifizierung, Berechtigungen, SSL",
            "configuration": "Konfigurationsfehler, fehlende Entities/Services",
            "system": "Systemressourcen (CPU, RAM, Disk)",
            "database": "Datenbankfehler, Locking",
            "automation": "Automatisierungsfehler",
            "device": "Geraetefehler, Erreichbarkeit, Batterie",
            "other": "Sonstige Fehler",
        },
    }

    response = client.post(
        "/api/v1/errors/repair-suggestions",
        json={
            "message": "Unexpected zigbee bridge hiccup",
            "context": "wohnzimmer offline",
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "message": "Unexpected zigbee bridge hiccup",
        "repairs": [
            {
                "category": "other",
                "severity": "medium",
                "suggestion": "1. Netzwerk pruefen\n2. Dienst neu starten",
                "actions": [],
                "source": "llm",
            }
        ],
        "pattern_matches": 0,
    }
    assert llm_provider.calls == [
        (
            "Du bist ein Smart-Home-Experte. Analysiere diesen Fehler und schlage "
            "konkrete Reparaturschritte vor (auf Deutsch, max 3 Schritte):\n\n"
            "Fehler: Unexpected zigbee bridge hiccup\n"
            "Kontext: wohnzimmer offline\n",
            300,
        )
    ]


def test_error_digest_contract_hardens_validation_and_runtime_errors(monkeypatch) -> None:
    llm_provider = FakeLLMProvider()
    client = _build_client(monkeypatch, llm_provider=llm_provider)

    response = client.get("/api/v1/errors/digest?hours=0")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "hours must be a positive integer"}

    response = client.get("/api/v1/errors/digest?severity=urgent")
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "severity must be one of: critical, high, low, medium",
    }

    monkeypatch.setattr(module, "_get_dev_logs", RaisingLogs())
    response = client.get("/api/v1/errors/digest")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "dev logs exploded"}

    response = client.post("/api/v1/errors/repair-suggestions", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}

    response = client.post("/api/v1/errors/repair-suggestions", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "message must be a non-empty string"}

    response = client.post("/api/v1/errors/repair-suggestions", json={"message": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "message must be a non-empty string"}

    response = client.post(
        "/api/v1/errors/repair-suggestions",
        json={"message": "Need context", "context": ["bad"]},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "context must be a string"}

    monkeypatch.setattr(module, "_match_repair_patterns", lambda _message: (_ for _ in ()).throw(RuntimeError("repair exploded")))
    response = client.post("/api/v1/errors/repair-suggestions", json={"message": "boom"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "repair exploded"}

    monkeypatch.setattr(module, "_match_repair_patterns", lambda _message: [])
    llm_provider.raise_on_generate = True
    response = client.post("/api/v1/errors/repair-suggestions", json={"message": "no pattern"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "message": "no pattern",
        "repairs": [],
        "pattern_matches": 0,
    }


def test_error_digest_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, llm_provider=None)

    response = client.get("/api/v1/errors/digest")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
