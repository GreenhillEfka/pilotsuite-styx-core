"""Minimal durable delivery intent store for DELIVERY-DURABILITY-304."""
from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_STORE_PATH = "/data/delivery_intents.jsonl"
_ENV_KEYS = (
    "PILOTSUITE_DELIVERY_INTENT_STORE_PATH",
    "DELIVERY_INTENT_STORE_PATH",
)


def _resolve_store_path(path: str | os.PathLike[str] | None = None) -> Path:
    if path:
        return Path(path)

    for env_key in _ENV_KEYS:
        value = os.environ.get(env_key, "").strip()
        if value:
            return Path(value)

    return Path(_DEFAULT_STORE_PATH)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize_datetime(value: datetime) -> str:
    return _to_utc(value).isoformat()


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _to_utc(value)

    parsed = datetime.fromisoformat(str(value))
    return _to_utc(parsed)


class DeliveryIntentStore:
    """Append-safe JSONL store keyed by delivery_token."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = _resolve_store_path(path)
        self.lock = threading.RLock()
        self.records: dict[str, dict[str, Any]] = {}
        self.last_error: str | None = None
        self.reload()

    def reload(self) -> bool:
        with self.lock:
            loaded: dict[str, dict[str, Any]] = {}
            if not self.path.exists():
                self.records.clear()
                self.last_error = None
                return True

            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    for line_number, raw_line in enumerate(handle, start=1):
                        line = raw_line.strip()
                        if not line:
                            continue
                        payload = json.loads(line)
                        record = self._deserialize_record(payload)
                        loaded[record["delivery_token"]] = record
            except Exception as exc:
                self.last_error = f"Delivery intent store load failed: {exc}"
                return False

            self.records.clear()
            self.records.update(loaded)
            self.last_error = None
            return True

    def get(self, delivery_token: str) -> dict[str, Any] | None:
        with self.lock:
            record = self.records.get(delivery_token)
            return deepcopy(record) if record is not None else None

    def put(self, record: dict[str, Any]) -> bool:
        normalized = self._normalize_record(record)
        with self.lock:
            if not self._append_record(normalized):
                return False
            self.records[normalized["delivery_token"]] = normalized
            self.last_error = None
            return True

    def _append_record(self, record: dict[str, Any]) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        self._serialize_record(record),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
            return True
        except Exception as exc:
            self.last_error = f"Delivery intent store write failed: {exc}"
            return False

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(record)
        normalized["delivery_token"] = str(normalized["delivery_token"])
        normalized["created_at"] = _parse_datetime(normalized["created_at"])
        normalized["updated_at"] = _parse_datetime(normalized["updated_at"])
        normalized["expires_at"] = _parse_datetime(normalized["expires_at"])
        normalized["attempt_count"] = int(normalized.get("attempt_count", 0))
        metadata = normalized.get("metadata")
        normalized["metadata"] = deepcopy(metadata) if metadata is not None else None
        return normalized

    def _serialize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(record)
        payload["created_at"] = _serialize_datetime(payload["created_at"])
        payload["updated_at"] = _serialize_datetime(payload["updated_at"])
        payload["expires_at"] = _serialize_datetime(payload["expires_at"])
        return payload

    def _deserialize_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = {
            "delivery_token",
            "state",
            "created_at",
            "updated_at",
            "expires_at",
            "last_action",
            "attempt_count",
        }
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"missing required fields: {sorted(missing)}")
        return self._normalize_record(payload)
