import json
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    """Canonical event envelope.

    Designed to map cleanly from HA event bus / state changes / intent results.
    """

    id: str
    ts: str
    type: str
    source: str = ""
    entity_id: str = ""
    user_id: str = ""
    text: str = ""
    attributes: dict[str, Any] | None = None

    # Optional idempotency / correlation fields as provided by upstream.
    event_id: str = ""
    idempotency_key: str = ""

    @staticmethod
    def from_payload(payload: dict[str, Any], *, idempotency_key: str = "") -> "Event":
        # Safe defaults; no validation explosions.
        upstream_event_id = str(payload.get("event_id") or "").strip()
        upstream_id = str(payload.get("id") or "").strip()

        # Canonical internal id: prefer explicit id, else explicit event_id, else generated.
        eid = upstream_id or upstream_event_id
        if not eid:
            eid = f"evt_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        ts = str(payload.get("ts") or payload.get("time") or payload.get("timestamp") or _now_iso())
        typ = str(payload.get("type") or payload.get("event_type") or "unknown")

        ik = str(idempotency_key or payload.get("idempotency_key") or "").strip()

        return Event(
            id=eid,
            ts=ts,
            type=typ,
            source=str(payload.get("source") or ""),
            entity_id=str(payload.get("entity_id") or ""),
            user_id=str(payload.get("user_id") or ""),
            text=str(payload.get("text") or payload.get("message") or ""),
            attributes=(payload.get("attributes") if isinstance(payload.get("attributes"), dict) else None),
            event_id=upstream_event_id,
            idempotency_key=ik,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "ts": self.ts,
            "type": self.type,
            "source": self.source,
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "text": self.text,
            "attributes": self.attributes or {},
        }

        if self.event_id:
            d["event_id"] = self.event_id
        if self.idempotency_key:
            d["idempotency_key"] = self.idempotency_key
        return d


class EventStore:
    """Small event ingest store.

    - Memory ring buffer always enabled.
    - Optional JSONL persistence for debugging/bootstrapping.
    - Optional idempotency/deduping based on an idempotency key.
    """

    def __init__(
        self,
        *,
        cache_max: int = 500,
        persist: bool = False,
        jsonl_path: str = "/data/events.jsonl",
        idempotency_ttl_seconds: int = 20 * 60,
        idempotency_lru_max: int = 10_000,
    ):
        self.cache_max = max(1, int(cache_max))
        self.persist = bool(persist)
        self.jsonl_path = jsonl_path

        self.idempotency_ttl_seconds = max(1, int(idempotency_ttl_seconds))
        self.idempotency_lru_max = max(0, int(idempotency_lru_max))

        self._cache: list[dict[str, Any]] = []

        # LRU(ish) TTL map: key -> expires_epoch_seconds
        self._seen: "OrderedDict[str, float]" = OrderedDict()
        # Stable response per key (best-effort, per-process)
        self._by_key: dict[str, dict[str, Any]] = {}

        # Load tail on boot if file exists
        if self.persist:
            self._load_tail()

    def _load_tail(self) -> None:
        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()[-self.cache_max :]
            for line in lines:
                try:
                    self._cache.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            return

    def _dedupe_key(self, payload: dict[str, Any], *, idempotency_key: str = "") -> str:
        """Compute idempotency key.

        Order of preference:
        - explicit idempotency key (header or payload)
        - event_id
        - id

        Empty string means "no dedupe".
        """

        if self.idempotency_lru_max <= 0:
            return ""

        ik = str(idempotency_key or payload.get("idempotency_key") or "").strip()
        if ik:
            return ik

        eid = str(payload.get("event_id") or "").strip()
        if eid:
            return f"event_id:{eid}"

        pid = str(payload.get("id") or "").strip()
        if pid:
            return f"id:{pid}"

        return ""

    def _prune_seen(self, now: float) -> None:
        # Drop expired keys from the front (oldest first).
        try:
            while self._seen:
                _, exp = next(iter(self._seen.items()))
                if exp >= now:
                    break
                k, _ = self._seen.popitem(last=False)
                self._by_key.pop(k, None)
        except Exception:
            return

        # Enforce max size (LRU)
        while self.idempotency_lru_max > 0 and len(self._seen) > self.idempotency_lru_max:
            k, _ = self._seen.popitem(last=False)
            self._by_key.pop(k, None)

    def append(self, payload: dict[str, Any], *, idempotency_key: str = "") -> tuple[dict[str, Any], bool]:
        """Append an event.

        Returns: (event_dict, stored)
        - stored=False means a duplicate was detected and nothing was persisted/added.
        """

        key = self._dedupe_key(payload, idempotency_key=idempotency_key)
        now = time.time()
        if key:
            self._prune_seen(now)
            exp = self._seen.get(key)
            if exp is not None and exp >= now:
                # Duplicate: return original response when possible.
                return (self._by_key.get(key) or {"idempotency_key": key, "duplicate": True}), False

        evt = Event.from_payload(payload, idempotency_key=idempotency_key).to_dict()
        evt["received"] = _now_iso()

        if key:
            self._seen[key] = now + float(self.idempotency_ttl_seconds)
            self._seen.move_to_end(key)

        if self.persist:
            os.makedirs(os.path.dirname(self.jsonl_path), exist_ok=True)
            with open(self.jsonl_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(evt, ensure_ascii=False) + "\n")

        self._cache.append(evt)
        if len(self._cache) > self.cache_max:
            del self._cache[: len(self._cache) - self.cache_max]

        if key:
            self._by_key[key] = evt
            self._prune_seen(now)

        return evt, True

    def extend(self, items: Iterable[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
        """Append many events.

        Returns: (stored_count, stored_events)
        """

        n = 0
        stored: list[dict[str, Any]] = []
        for it in items:
            try:
                evt, ok = self.append(it)
                if ok:
                    stored.append(evt)
                    n += 1
            except Exception:
                continue
        return n, stored

    def list(self, *, limit: int = 50, since_ts: Optional[str] = None) -> list[dict[str, Any]]:
        items = self._cache
        if since_ts:
            # naive filter (string compare works for ISO8601; good enough for scaffold)
            items = [e for e in items if str(e.get("ts", "")) >= since_ts]
        limit = max(1, min(int(limit), self.cache_max))
        return items[-limit:]
