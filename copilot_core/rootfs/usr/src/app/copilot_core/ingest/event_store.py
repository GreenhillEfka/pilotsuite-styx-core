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
_KIND_ALIASES = {"service_call": "call_service"}

# Allowed source identifiers
_ALLOWED_SOURCES = {"ha", "home_assistant"}
_SOURCE_ALIASES = {"home_assistant": "ha", "homeassistant": "ha"}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _nested_context(event: dict[str, Any]) -> dict[str, Any]:
    habitat_event = _as_dict(event.get("habitat_event"))
    neuron_input = _as_dict(event.get("neuron_input"))
    return {
        "habitat_event": habitat_event,
        "habitat_attrs": _as_dict(habitat_event.get("attributes")),
        "habitat_context": _as_dict(habitat_event.get("context")),
        "habitat_state": _as_dict(habitat_event.get("state")),
        "neuron_input": neuron_input,
        "neuron_context": _as_dict(neuron_input.get("context")),
        "neuron_metadata": _as_dict(neuron_input.get("metadata")),
        "adapter": _as_dict(event.get("adapter")),
    }


def _extract_kind(event: dict[str, Any]) -> str:
    nested = _nested_context(event)
    raw = _first_present(
        event.get("kind"),
        event.get("type"),
        nested["habitat_event"].get("event_type"),
        nested["adapter"].get("event_type"),
        nested["neuron_context"].get("event_type"),
        "",
    )
    return _canonical_kind(raw)


def _extract_source(event: dict[str, Any]) -> str:
    nested = _nested_context(event)
    raw = _first_present(
        event.get("src"),
        event.get("source"),
        nested["habitat_context"].get("source"),
        nested["neuron_context"].get("source"),
        nested["adapter"].get("name"),
        "",
    )
    return _canonical_source(raw)


def _extract_entity_id(event: dict[str, Any]) -> str:
    nested = _nested_context(event)
    return str(
        _first_present(
            event.get("entity_id"),
            nested["habitat_event"].get("entity_id"),
            nested["neuron_input"].get("entity_id"),
            "",
        )
        or ""
    )


def _extract_ts(event: dict[str, Any]) -> str:
    nested = _nested_context(event)
    return str(
        _first_present(
            event.get("ts"),
            nested["habitat_context"].get("ts"),
            nested["neuron_context"].get("ts"),
            "",
        )
        or ""
    )


def _extract_zone_ids(event: dict[str, Any]) -> list[str]:
    nested = _nested_context(event)
    zone_ids = _first_present(
        event.get("zone_ids"),
        _as_dict(event.get("attributes")).get("zone_ids"),
        nested["habitat_attrs"].get("zone_ids"),
        nested["neuron_metadata"].get("zone_ids"),
        event.get("zone_id"),
        nested["habitat_event"].get("zone_id"),
        nested["neuron_input"].get("zone_id"),
    )
    return _listify_strs(zone_ids)


def _extract_service_payload(event: dict[str, Any]) -> dict[str, Any]:
    nested = _nested_context(event)
    attrs = _as_dict(event.get("attributes"))
    service_payload = _as_dict(event.get("service"))
    return {
        "domain": str(
            _first_present(
                service_payload.get("domain"),
                event.get("domain"),
                attrs.get("domain"),
                nested["habitat_state"].get("domain"),
                nested["habitat_attrs"].get("domain"),
                nested["neuron_input"].get("domain"),
                "",
            )
            or ""
        ),
        "service": str(
            _first_present(
                service_payload.get("service"),
                attrs.get("service"),
                event.get("service") if not isinstance(event.get("service"), dict) else None,
                nested["habitat_state"].get("service"),
                nested["habitat_attrs"].get("service"),
                "",
            )
            or ""
        ),
        "entity_ids": _listify_strs(
            _first_present(
                service_payload.get("entity_ids"),
                attrs.get("entity_ids"),
                nested["habitat_state"].get("entity_ids"),
                nested["habitat_attrs"].get("entity_ids"),
                nested["neuron_metadata"].get("entity_ids"),
                event.get("entity_id"),
                nested["habitat_event"].get("entity_id"),
                [],
            )
        ),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_kind(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return _KIND_ALIASES.get(raw, raw)


def _canonical_source(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return _SOURCE_ALIASES.get(raw, raw)


def _listify_strs(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _truncate_context_id(value: Any) -> str:
    value = str(value or "")
    return value[:12] if len(value) > 12 else value


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
        except (IOError, json.JSONDecodeError) as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to load event store tail: %s", exc)

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

        # Gradual eviction: remove oldest 25% when exceeding 2x max
        # This avoids oscillation from the previous 50% drop strategy
        max_dedup_size = self._max * 2
        if len(self._seen) > max_dedup_size:
            evict_count = max_dedup_size // 4
            keys_to_remove = list(self._seen.keys())[:evict_count]
            for k in keys_to_remove:
                self._seen.pop(k, None)

        return False

    def validate_event(self, event: dict[str, Any]) -> str | None:
        """Validate a single event envelope. Returns error string or None if valid."""
        if not isinstance(event, dict):
            return "event must be a dict"

        # Normalize: accept both forwarder formats and nested adapter envelopes
        # HA forwarder uses "type" + "source"; N3 spec uses "kind" + "src"
        kind = _extract_kind(event)
        src = _extract_source(event)

        if not kind:
            return "missing 'kind' or 'type'"
        if not src:
            return "missing 'src' or 'source'"

        if kind not in _ALLOWED_KINDS:
            return f"unsupported kind: {kind}"

        if src not in {"ha", *(_ALLOWED_SOURCES - {"ha"})}:
            return f"unsupported source: {src}"

        attrs = event.get("attributes") if isinstance(event.get("attributes"), dict) else {}
        service_payload = _extract_service_payload(event)
        entity_id = _extract_entity_id(event)
        ts = _extract_ts(event)

        if kind == "state_changed" and not entity_id:
            return "missing 'entity_id' for state_changed event"

        if kind == "call_service":
            service_domain = service_payload.get("domain") or event.get("domain") or attrs.get("domain")
            service_name = service_payload.get("service") or event.get("service") or attrs.get("service")
            if not service_domain or not service_name:
                return "missing service.domain/service for call_service event"

        if not ts:
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
        nested = _nested_context(event)
        kind = _extract_kind(event)
        src = _extract_source(event)

        # Extract attrs from both formats
        attrs = event.get("attributes") if isinstance(event.get("attributes"), dict) else {}
        zone_ids = _extract_zone_ids(event)
        zone_id = zone_ids[0] if zone_ids else ""
        entity_id = _extract_entity_id(event)
        ts = _extract_ts(event)

        normalized: dict[str, Any] = {
            "v": event.get("v", 1),
            "id": dedup_key,
            "ts": ts,
            "ingested_at": _now_iso(),
            "kind": kind,
            "src": src,
            "entity_id": entity_id,
            "domain": str(
                _first_present(
                    attrs.get("domain"),
                    event.get("domain"),
                    nested["habitat_event"].get("domain"),
                    nested["habitat_attrs"].get("domain"),
                    nested["neuron_input"].get("domain"),
                    nested["habitat_event"].get("module_id"),
                    nested["neuron_input"].get("module_id"),
                    "",
                )
                or ""
            ),
            "zone_ids": zone_ids,
            "zone_id": zone_id,
        }

        # State delta (support both N3 spec format and current forwarder format)
        if kind == "state_changed":
            # N3 spec: old/new objects with state+attrs
            if "old" in event and "new" in event:
                normalized["old"] = event["old"]
                normalized["new"] = event["new"]
            else:
                # Forwarder/adaptor fallback: flat attributes or nested habitat/neuron metadata
                normalized["old"] = {
                    "state": _first_present(
                        attrs.get("old_state"),
                        nested["habitat_attrs"].get("old_state"),
                        nested["neuron_metadata"].get("old_state"),
                    ),
                    "attrs": attrs.get("old_attrs") or nested["habitat_attrs"].get("old_attrs") or {},
                }
                normalized["new"] = {
                    "state": _first_present(
                        attrs.get("new_state"),
                        nested["habitat_attrs"].get("new_state"),
                        nested["neuron_metadata"].get("new_state"),
                        nested["habitat_event"].get("state"),
                        nested["neuron_input"].get("value"),
                    ),
                    "attrs": _first_present(
                        attrs.get("state_attributes"),
                        attrs.get("new_attrs"),
                        nested["habitat_attrs"].get("state_attributes"),
                        nested["habitat_attrs"].get("new_attrs"),
                        nested["neuron_metadata"].get("state_attributes"),
                        {},
                    )
                    or {},
                }

        elif kind == "call_service":
            service_payload = _extract_service_payload(event)
            normalized["service"] = service_payload

        elif kind == "heartbeat":
            normalized["entity_count"] = event.get("entity_count", 0)

        # Context (truncated per N3 spec / privacy budget)
        raw_context = event.get("context") if isinstance(event.get("context"), dict) else {}
        ctx_id = _truncate_context_id(raw_context.get("id") or event.get("context_id"))
        ctx_parent_id = _truncate_context_id(raw_context.get("parent_id") or event.get("context_parent_id"))
        ctx_user_id = _truncate_context_id(raw_context.get("user_id") or event.get("context_user_id"))
        normalized["context_id"] = ctx_id
        normalized["context_parent_id"] = ctx_parent_id
        normalized["context_user_id"] = ctx_user_id
        if ctx_id or ctx_parent_id or ctx_user_id:
            normalized["context"] = {
                "id": ctx_id,
                "parent_id": ctx_parent_id,
                "user_id": ctx_user_id,
            }

        normalized["trigger"] = event.get("trigger") or attrs.get("trigger") or "unknown"

        return normalized

    def _append_jsonl(self, event: dict[str, Any]) -> None:
        """Append a single event to the JSONL file."""
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
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
