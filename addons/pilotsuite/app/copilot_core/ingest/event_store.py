"""Bounded event store with JSONL persistence and in-memory ring buffer.

Privacy-first: events are validated against an envelope schema before storage.
No raw HA payloads are persisted — only the stable CoPilot envelope format.

Environment variables:
    COPILOT_EVENT_STORE_PATH  – JSONL file path (default: /data/events.jsonl)
    COPILOT_EVENT_STORE_MAX   – max events in memory ring (default: 5000)
    COPILOT_EVENT_STORE_DEDUP_TTL – dedup window in seconds (default: 120)
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any


_DEFAULT_STORE_PATH = "/data/events.jsonl"
_DEFAULT_MAX_EVENTS = 5000
_DEFAULT_DEDUP_TTL = 120  # seconds

# Allowed envelope versions (for forward-compat)
_SUPPORTED_VERSIONS = {1}

# Allowed event kinds
_ALLOWED_KINDS = {"state_changed", "call_service", "heartbeat"}

# Allowed source identifiers
_ALLOWED_SOURCES = {"ha", "home_assistant"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_dedup_key(event: dict[str, Any]) -> str:
    """Deterministic dedup key from event envelope.

    Uses event id if present, otherwise hashes core fields.
    """
    eid = event.get("id")
    if isinstance(eid, str) and eid:
        return eid

    # Fallback: hash entity_id + type + ts
    parts = [
        str(event.get("entity_id", "")),
        str(event.get("type", event.get("kind", ""))),
        str(event.get("ts", "")),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


class EventStore:
    """Thread-safe bounded event store with JSONL append and dedup."""

    def __init__(
        self,
        store_path: str | None = None,
        max_events: int | None = None,
        dedup_ttl: int | None = None,
    ) -> None:
        self._path = store_path or os.environ.get(
            "COPILOT_EVENT_STORE_PATH", _DEFAULT_STORE_PATH
        )
        self._max = max_events if max_events is not None else int(
            os.environ.get("COPILOT_EVENT_STORE_MAX", _DEFAULT_MAX_EVENTS)
        )
        self._dedup_ttl = dedup_ttl if dedup_ttl is not None else int(
            os.environ.get("COPILOT_EVENT_STORE_DEDUP_TTL", _DEFAULT_DEDUP_TTL)
        )

        self._lock = threading.Lock()
        self._ring: list[dict[str, Any]] = []
        self._seen: OrderedDict[str, float] = OrderedDict()  # key → expiry_ts

        # Stats
        self.accepted_total: int = 0
        self.rejected_total: int = 0
        self.deduped_total: int = 0

        # Load tail from JSONL on init
        self._load_tail()

    def _load_tail(self) -> None:
        """Load last N events from JSONL into memory ring."""
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
            tail = lines[-self._max:] if len(lines) > self._max else lines
            for line in tail:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._ring.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def _prune_seen(self) -> None:
        """Remove ALL expired dedup entries (call under lock).
        
        FIX: Now removes ALL expired entries, not just until first non-expired.
        This prevents unbounded growth when events arrive with old timestamps.
        """
        now = time.time()
        # Remove ALL expired entries (not just until first non-expired)
        expired_keys = [k for k, expiry in self._seen.items() if expiry <= now]
        for key in expired_keys:
            self._seen.pop(key, None)

    def _is_duplicate(self, key: str) -> bool:
        """Check and register dedup key (call under lock).
        
        FIX: Added periodic full prune to prevent memory leak.
        """
        if self._dedup_ttl <= 0:
            return False

        # FIX: Periodic full prune every 100 calls to prevent memory leak
        # Use modulo to avoid expensive pruning on every call
        if self.accepted_total % 100 == 0:
            self._prune_seen()

        now = time.time()
        if key in self._seen and self._seen[key] > now:
            return True

        self._seen[key] = now + self._dedup_ttl
        
        # FIX: More aggressive bound enforcement
        # Bound dedup map - keep it bounded to 2x max events
        max_dedup_size = self._max * 2
        if len(self._seen) > max_dedup_size:
            # Remove oldest 50% of entries
            keys_to_remove = list(self._seen.keys())[:max_dedup_size // 2]
            for key in keys_to_remove:
                self._seen.pop(key, None)

        return False

    def validate_event(self, event: dict[str, Any]) -> str | None:
        """Validate a single event envelope. Returns error string or None if valid."""
        if not isinstance(event, dict):
            return "event must be a dict"

        # Normalize: accept both forwarder formats
        # HA forwarder uses "type" + "source"; N3 spec uses "kind" + "src"
        kind = event.get("kind") or event.get("type")
        src = event.get("src") or event.get("source")

        if not kind:
            return "missing 'kind' or 'type'"
        if not src:
            return "missing 'src' or 'source'"

        # We accept both naming conventions
        if kind not in _ALLOWED_KINDS and kind not in {"state_changed", "call_service", "heartbeat"}:
            return f"unsupported kind: {kind}"

        if src not in _ALLOWED_SOURCES:
            return f"unsupported source: {src}"

        if not event.get("entity_id") and kind != "heartbeat":
            return "missing 'entity_id' for non-heartbeat event"

        if not event.get("ts"):
            return "missing 'ts'"

        return None

    def ingest_batch(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Ingest a batch of event envelopes.

        Returns summary dict with accepted/rejected/deduped counts
        and the list of accepted (normalized) events.
        """
        accepted = 0
        rejected = 0
        deduped = 0
        errors: list[dict[str, Any]] = []
        accepted_events: list[dict[str, Any]] = []

        with self._lock:
            for i, item in enumerate(items):
                err = self.validate_event(item)
                if err:
                    rejected += 1
                    self.rejected_total += 1
                    errors.append({"index": i, "error": err})
                    continue

                dedup_key = _compute_dedup_key(item)
                if self._is_duplicate(dedup_key):
                    deduped += 1
                    self.deduped_total += 1
                    continue

                # Normalize to canonical envelope
                normalized = self._normalize(item, dedup_key)

                # Append to ring
                self._ring.append(normalized)
                if len(self._ring) > self._max:
                    del self._ring[:len(self._ring) - self._max]

                # Persist
                self._append_jsonl(normalized)

                accepted += 1
                self.accepted_total += 1
                accepted_events.append(normalized)

        return {
            "accepted": accepted,
            "rejected": rejected,
            "deduped": deduped,
            "errors": errors[:10],  # cap error details
            "accepted_events": accepted_events,
        }

    def _normalize(self, event: dict[str, Any], dedup_key: str) -> dict[str, Any]:
        """Normalize forwarder envelope to canonical Core format."""
        kind = event.get("kind") or event.get("type", "unknown")
        src = event.get("src") or event.get("source", "unknown")

        # Extract attrs from both formats
        attrs = event.get("attributes", {})

        normalized: dict[str, Any] = {
            "v": event.get("v", 1),
            "id": dedup_key,
            "ts": event.get("ts"),
            "ingested_at": _now_iso(),
            "kind": kind,
            "src": src,
            "entity_id": event.get("entity_id", ""),
            "domain": attrs.get("domain") or event.get("domain", ""),
        }

        # State delta (support both N3 spec format and current forwarder format)
        if kind == "state_changed":
            # N3 spec: old/new objects with state+attrs
            if "old" in event and "new" in event:
                normalized["old"] = event["old"]
                normalized["new"] = event["new"]
            else:
                # Current forwarder: flat in attributes
                normalized["old"] = {
                    "state": attrs.get("old_state"),
                    "attrs": {},
                }
                normalized["new"] = {
                    "state": attrs.get("new_state"),
                    "attrs": attrs.get("state_attributes", {}),
                }

            # Zone info
            zone_ids = attrs.get("zone_ids") or event.get("zone_id")
            if isinstance(zone_ids, str):
                zone_ids = [zone_ids]
            normalized["zone_ids"] = zone_ids or []

        elif kind == "call_service":
            normalized["service"] = {
                "domain": attrs.get("domain", ""),
                "service": attrs.get("service", ""),
                "entity_ids": attrs.get("entity_ids", []),
            }
            normalized["zone_ids"] = attrs.get("zone_ids", [])

        elif kind == "heartbeat":
            normalized["entity_count"] = event.get("entity_count", 0)

        # Context (truncated per N3 spec)
        ctx_id = event.get("context_id", "")
        if isinstance(ctx_id, str) and len(ctx_id) > 12:
            ctx_id = ctx_id[:12]
        normalized["context_id"] = ctx_id

        normalized["trigger"] = event.get("trigger", "unknown")

        return normalized

    def _append_jsonl(self, event: dict[str, Any]) -> None:
        """Append a single event to the JSONL file."""
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Best-effort persistence

    def query(
        self,
        domain: str | None = None,
        entity_id: str | None = None,
        kind: str | None = None,
        zone_id: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query events from the in-memory ring buffer with optional filters."""
        limit = max(1, min(limit, 1000))

        with self._lock:
            results: list[dict[str, Any]] = []
            for ev in reversed(self._ring):
                if domain and ev.get("domain") != domain:
                    continue
                if entity_id and ev.get("entity_id") != entity_id:
                    continue
                if kind and ev.get("kind") != kind:
                    continue
                if zone_id:
                    zones = ev.get("zone_ids", [])
                    if zone_id not in zones:
                        continue
                if since and ev.get("ts", "") < since:
                    continue

                results.append(ev)
                if len(results) >= limit:
                    break

            results.reverse()
            return results

    def stats(self) -> dict[str, Any]:
        """Return store statistics."""
        with self._lock:
            return {
                "buffered": len(self._ring),
                "max_buffer": self._max,
                "dedup_window_s": self._dedup_ttl,
                "accepted_total": self.accepted_total,
                "rejected_total": self.rejected_total,
                "deduped_total": self.deduped_total,
                "dedup_keys_tracked": len(self._seen),
            }
