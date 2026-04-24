from __future__ import annotations

from contextlib import contextmanager
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from unittest.mock import patch

import copilot_core.api.v1.delivery_interactive as delivery_interactive
from copilot_core.api.v1.delivery_interactive import DeliveryState, delivery_bp
from copilot_core.api.v1.delivery_intent_store import DeliveryIntentStore


class _FailingWriteStore:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}
        self.lock = threading.RLock()
        self.last_error: str | None = None

    def get(self, delivery_token: str):
        record = self.records.get(delivery_token)
        return None if record is None else dict(record)

    def put(self, record: dict) -> bool:
        self.last_error = "Delivery intent store write failed: injected fault"
        return False


@contextmanager
def _with_temp_store(tmp_path):
    original_store = delivery_interactive._intent_store
    temp_store = DeliveryIntentStore(tmp_path / "delivery_intents.jsonl")
    delivery_interactive._set_delivery_intent_store_for_testing(temp_store)
    try:
        yield temp_store
    finally:
        delivery_interactive._set_delivery_intent_store_for_testing(original_store)


def _make_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(delivery_bp)
    return app


def _make_token() -> str:
    return str(uuid.uuid4())


def _with_auth():
    return patch("copilot_core.api.security.validate_token", return_value=True)


class TestDeliveryDurability304:
    def test_reacknowledge_remains_idempotent_after_store_reload(self, tmp_path):
        app = _make_app()
        token = _make_token()

        with _with_temp_store(tmp_path) as store, _with_auth():
            client = app.test_client()
            first = client.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"},
            ).get_json()
            reloaded = DeliveryIntentStore(store.path)
            delivery_interactive._set_delivery_intent_store_for_testing(reloaded)
            second = client.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"},
            ).get_json()

            assert first["state"] == second["state"] == DeliveryState.ACKNOWLEDGED.value
            assert reloaded.get(token)["attempt_count"] == 1

    def test_cancel_remains_terminal_after_store_reload(self, tmp_path):
        app = _make_app()
        token = _make_token()

        with _with_temp_store(tmp_path) as store, _with_auth():
            client = app.test_client()
            client.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"},
            )
            client.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "cancel"},
            )
            reloaded = DeliveryIntentStore(store.path)
            delivery_interactive._set_delivery_intent_store_for_testing(reloaded)
            response = client.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"},
            ).get_json()

            assert response["state"] == DeliveryState.CANCELLED.value
            assert reloaded.get(token)["state"] == DeliveryState.CANCELLED.value

    def test_expired_token_cannot_be_revived_after_store_reload(self, tmp_path):
        app = _make_app()
        token = _make_token()
        now = datetime.now(timezone.utc)

        with _with_temp_store(tmp_path) as store, _with_auth():
            assert store.put(
                {
                    "delivery_token": token,
                    "state": DeliveryState.ACKNOWLEDGED.value,
                    "created_at": now - timedelta(minutes=10),
                    "updated_at": now - timedelta(minutes=10),
                    "expires_at": now - timedelta(minutes=5),
                    "last_action": "acknowledge",
                    "attempt_count": 1,
                    "metadata": {"source": "durability-test"},
                }
            )
            reloaded = DeliveryIntentStore(store.path)
            delivery_interactive._set_delivery_intent_store_for_testing(reloaded)
            response = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"},
            ).get_json()

            assert response["state"] == DeliveryState.EXPIRED.value
            assert reloaded.get(token)["state"] == DeliveryState.EXPIRED.value

    def test_duplicate_cancel_attempts_do_not_diverge_state(self, tmp_path):
        app = _make_app()
        token = _make_token()

        with _with_temp_store(tmp_path) as store, _with_auth():
            client = app.test_client()
            first = client.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "cancel"},
            ).get_json()
            second = client.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "cancel"},
            ).get_json()
            stored = store.get(token)

            assert first["state"] == second["state"] == DeliveryState.CANCELLED.value
            assert stored["state"] == DeliveryState.CANCELLED.value
            assert stored["attempt_count"] == 2

    def test_unknown_token_status_remains_pending_without_persisting_record(self, tmp_path):
        app = _make_app()
        token = _make_token()

        with _with_temp_store(tmp_path) as store, _with_auth():
            response = app.test_client().get(f"/api/v1/delivery/{token}/status").get_json()

            assert response["state"] == DeliveryState.PENDING.value
            assert store.get(token) is None

    def test_persistence_write_fault_returns_explicit_non_success(self):
        app = _make_app()
        original_store = delivery_interactive._intent_store
        try:
            delivery_interactive._set_delivery_intent_store_for_testing(_FailingWriteStore())
            with _with_auth():
                response = app.test_client().post(
                    "/api/v1/delivery/acknowledge",
                    json={"delivery_token": _make_token(), "action": "acknowledge"},
                )
            payload = response.get_json()

            assert response.status_code == 503
            assert payload["ok"] is False
            assert "store" in payload["error"].lower()
        finally:
            delivery_interactive._set_delivery_intent_store_for_testing(original_store)
