"""
Event processing pipeline connecting EventStore to BrainGraphService.

This module provides automatic processing of ingested events to update
the brain graph with real-time smart home state and relationships.
Includes auto-triggered habitus mining after event ingestion.
"""

import logging
import os
import threading
import time
from typing import Dict, Any, Optional, Callable, List, Set
from ..brain_graph.service import BrainGraphService
from ..brain_read_model import feed_brain
from ..dev_surface.service import dev_surface

logger = logging.getLogger(__name__)

# Auto-mining thresholds (configurable via env vars)
_AUTO_MINE_EVENT_THRESHOLD = int(os.environ.get("HABITUS_AUTO_MINE_EVENT_THRESHOLD", "1000"))
_AUTO_MINE_INTERVAL_S = int(os.environ.get("HABITUS_AUTO_MINE_INTERVAL_S", "3600"))


class EventProcessor:
    """
    Processes events from EventStore and forwards them to downstream services.

    Currently supports:
    - BrainGraphService integration for knowledge graph updates
    - Configurable event filters and processors
    - Rollback on batch failure (only commits successfully processed events)
    - Idempotency via event ID deduplication
    - Auto-triggered habitus mining (every N events or M seconds)
    """

    def __init__(self, brain_graph_service: Optional[BrainGraphService] = None):
        self.brain_graph_service = brain_graph_service
        self.processors: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()
        # Idempotency: track recently processed event IDs
        self._processed_ids: Set[str] = set()
        self._max_processed_ids = 10000

        # Auto-mining state
        self._habitus_miner = None  # set via set_habitus_miner()
        self._events_since_last_mine: int = 0
        self._last_mine_ts: float = time.time()
        self._mine_lock = threading.Lock()
        self._mining_in_progress: bool = False
        self._habitus_event_buffer: List[Dict[str, Any]] = []

        # Register default processors
        if brain_graph_service:
            self.processors.append(self._process_for_brain_graph)

    def set_habitus_miner(self, miner) -> None:
        """Inject a HabitusMinerService for auto-triggered mining.

        Once set, the processor will automatically trigger habitus mining
        after every ``HABITUS_AUTO_MINE_EVENT_THRESHOLD`` processed events
        or every ``HABITUS_AUTO_MINE_INTERVAL_S`` seconds (whichever comes
        first).  Mining runs in a background thread so it never blocks
        event processing.
        """
        self._habitus_miner = miner
        logger.info(
            "Habitus auto-mining enabled (threshold=%d events, interval=%ds)",
            _AUTO_MINE_EVENT_THRESHOLD,
            _AUTO_MINE_INTERVAL_S,
        )

    def add_processor(self, processor: Callable[[Dict[str, Any]], None]):
        """Add a custom event processor function."""
        self.processors.append(processor)

    def process_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch of events through all registered processors.

        Only commits successfully processed events to brain graph.
        Skips duplicate events (idempotency check).

        Args:
            events: List of normalized event dictionaries from EventStore

        Returns:
            Processing statistics
        """
        stats = {
            "processed": 0,
            "errors": 0,
            "skipped_duplicate": 0,
            "brain_graph_updates": 0,
        }

        with self._lock:
            # Deduplicate: filter out already-processed events
            unique_events = []
            for event in events:
                event_id = event.get("id", "")
                if event_id and event_id in self._processed_ids:
                    stats["skipped_duplicate"] += 1
                    continue
                unique_events.append(event)

            if not unique_events:
                return stats

            # Use batch mode for brain graph performance
            if self.brain_graph_service:
                self.brain_graph_service.begin_batch(size=len(unique_events))

            successful_events = []
            for event in unique_events:
                try:
                    for processor in self.processors:
                        processor(event)
                    # Explicit brain feed: transfer event into Brain Read Model
                    # (after/normal to normal processing as specified in Slice 5)
                    feed_brain(event)
                    stats["processed"] += 1
                    successful_events.append(event)
                except Exception as e:
                    logger.error("Error processing event %s: %s", event.get("id", "unknown"), e)
                    dev_surface.error(
                        "event_processor",
                        f"Failed to process event {event.get('id', 'unknown')}",
                        error=e,
                        context={"event": event},
                    )
                    stats["errors"] += 1

            # Only commit batch if at least some events succeeded
            if self.brain_graph_service:
                if successful_events:
                    self.brain_graph_service.commit_batch()
                else:
                    self.brain_graph_service.rollback_batch()
                    logger.warning("All %d events failed; batch rolled back", len(unique_events))

            # Record successfully processed IDs for idempotency
            for event in successful_events:
                event_id = event.get("id", "")
                if event_id:
                    self._processed_ids.add(event_id)
            # Prune old IDs to bound memory
            if len(self._processed_ids) > self._max_processed_ids:
                self._processed_ids = set()

        # Track processed events for metrics
        dev_surface.increment_events_processed(stats["processed"])

        if stats["processed"] > 0:
            dev_surface.debug("event_processor", f"Processed {stats['processed']} events successfully")

        # Auto-mining: buffer events and check trigger conditions
        if self._habitus_miner and stats["processed"] > 0:
            self._buffer_for_mining(events)
            self._maybe_trigger_mining()

        return stats

    # ── Habitus auto-mining helpers ─────────────────────────────────

    def _buffer_for_mining(self, events: List[Dict[str, Any]]) -> None:
        """Convert processed events to HA-like format and buffer them."""
        ha_events = []
        for evt in events:
            if not isinstance(evt, dict):
                continue
            entity_id = evt.get("entity_id", "")
            attrs = evt.get("attributes") if isinstance(evt.get("attributes"), dict) else {}
            old_state = attrs.get("old_state", "")
            new_state = attrs.get("new_state", "")

            # Also check canonical normalized snapshots.
            if not old_state and isinstance(evt.get("old"), dict):
                old_state = evt["old"].get("state", "")
            if not new_state and isinstance(evt.get("new"), dict):
                new_state = evt["new"].get("state", "")

            if not entity_id or not new_state:
                continue
            ha_events.append({
                "event_type": "state_changed",
                "time_fired": evt.get("ts") or evt.get("timestamp", ""),
                "data": {
                    "entity_id": entity_id,
                    "old_state": {"state": old_state} if old_state else None,
                    "new_state": {"state": new_state},
                },
            })

        if not ha_events:
            return

        with self._mine_lock:
            self._habitus_event_buffer.extend(ha_events)
            self._events_since_last_mine += len(ha_events)

    def _maybe_trigger_mining(self) -> None:
        """Check if auto-mining should fire (count or time threshold)."""
        with self._mine_lock:
            if self._mining_in_progress:
                return

            elapsed = time.time() - self._last_mine_ts
            count = self._events_since_last_mine

            should_mine = (
                count >= _AUTO_MINE_EVENT_THRESHOLD
                or (count > 0 and elapsed >= _AUTO_MINE_INTERVAL_S)
            )

            if not should_mine:
                return

            # Grab the buffer and reset counters
            batch = list(self._habitus_event_buffer)
            self._habitus_event_buffer.clear()
            self._events_since_last_mine = 0
            self._last_mine_ts = time.time()
            self._mining_in_progress = True

        # Fire mining in a background thread (non-blocking)
        logger.info(
            "Auto-mining triggered: %d buffered events (count=%d, elapsed=%.0fs)",
            len(batch), count, elapsed,
        )
        thread = threading.Thread(
            target=self._run_mining,
            args=(batch,),
            name="habitus-auto-mine",
            daemon=True,
        )
        thread.start()

    def _run_mining(self, ha_events: List[Dict[str, Any]]) -> None:
        """Execute habitus mining in background thread (exception-safe)."""
        try:
            miner = self._habitus_miner
            if miner is None:
                return
            rules = miner.mine_from_ha_events(ha_events)
            logger.info(
                "Auto-mining completed: %d events -> %d rules",
                len(ha_events), len(rules),
            )
        except Exception:
            logger.exception("Auto-mining failed (non-fatal)")
        finally:
            with self._mine_lock:
                self._mining_in_progress = False

    # ── Brain graph processors ───────────────────────────────────────

    @staticmethod
    def _primary_zone_id(event: Dict[str, Any]) -> str:
        zone_id = str(event.get("zone_id") or "").strip()
        if zone_id:
            return zone_id
        zone_ids = event.get("zone_ids")
        if isinstance(zone_ids, list):
            for candidate in zone_ids:
                candidate = str(candidate).strip()
                if candidate:
                    return candidate
        return ""

    @staticmethod
    def _service_details(event: Dict[str, Any]) -> tuple[str, str, list[str]]:
        service_payload = event.get("service") if isinstance(event.get("service"), dict) else {}
        domain = str(service_payload.get("domain") or event.get("domain") or "").strip()
        service = str(service_payload.get("service") or event.get("service") or "").strip()

        entity_ids = service_payload.get("entity_ids")
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        elif not isinstance(entity_ids, list):
            entity_ids = []

        normalized_entity_ids: list[str] = []
        for entity_id in entity_ids:
            entity_id = str(entity_id).strip()
            if entity_id and entity_id not in normalized_entity_ids:
                normalized_entity_ids.append(entity_id)

        fallback_entity_id = str(event.get("entity_id") or "").strip()
        if fallback_entity_id and fallback_entity_id not in normalized_entity_ids:
            normalized_entity_ids.append(fallback_entity_id)

        return domain, service, normalized_entity_ids

    def _process_for_brain_graph(self, event: Dict[str, Any]):
        """Process event for brain graph updates."""
        if not self.brain_graph_service:
            return

        try:
            kind = event.get("kind", "")

            if kind == "state_changed":
                self._process_state_change_for_graph(event)
            elif kind == "call_service":
                self._process_service_call_for_graph(event)

        except Exception as e:
            logger.error("Brain graph processing error for event %s: %s", event.get("id"), e)

    def _process_state_change_for_graph(self, event: Dict[str, Any]):
        """Process state_changed events for brain graph."""
        entity_id = event.get("entity_id", "")
        domain = event.get("domain", "")
        zone_id = self._primary_zone_id(event)

        if not entity_id or not domain:
            return

        # Create/touch entity node
        entity_label = entity_id.split(".")[-1].replace("_", " ").title()

        node_meta = {}
        if zone_id:
            node_meta["zone_id"] = zone_id

        # Get new state info if available
        new_state = event.get("new", {})
        if new_state:
            state_value = new_state.get("state")
            if state_value:
                node_meta["last_state"] = state_value

        entity_node = self.brain_graph_service.touch_node(
            node_id=f"ha.entity:{entity_id}",
            delta=0.5,  # Moderate score boost for state changes
            label=entity_label,
            kind="entity",
            domain=domain,
            meta_patch=node_meta,
            source={"system": "ha", "event": "state_changed"},
            tags=[f"domain:{domain}"]
        )

        # Create zone node and link if zone_id exists
        if zone_id:
            zone_node = self.brain_graph_service.touch_node(
                node_id=f"ha.zone:{zone_id}",
                delta=0.1,  # Small boost for zones
                label=zone_id.replace("_", " ").title(),
                kind="zone",
                domain="zone",
                source={"system": "ha", "event": "state_changed"}
            )

            # Link entity to zone
            self.brain_graph_service.link(
                from_node=entity_node.id,
                to_node=zone_node.id,
                edge_type="located_in",
                initial_weight=0.3
            )

    def _process_service_call_for_graph(self, event: Dict[str, Any]):
        """Process call_service events for brain graph."""
        domain, service, entity_ids = self._service_details(event)

        if not domain or not service:
            return

        # Create/touch service node
        service_node_id = f"ha.service:{domain}.{service}"
        service_node = self.brain_graph_service.touch_node(
            node_id=service_node_id,
            delta=0.8,  # Higher score for service calls (intentional actions)
            label=f"{service.replace('_', ' ').title()}",
            kind="service",
            domain=domain,
            source={"system": "ha", "event": "call_service"},
            tags=[f"domain:{domain}", f"service:{service}"]
        )

        for entity_id in entity_ids:
            entity_domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            entity_label = entity_id.split(".")[-1].replace("_", " ").title() if "." in entity_id else entity_id
            entity_node = self.brain_graph_service.touch_node(
                node_id=f"ha.entity:{entity_id}",
                delta=0.3,  # Boost for being target of service call
                label=entity_label,
                kind="entity",
                domain=entity_domain,
                source={"system": "ha", "event": "call_service"}
            )

            # Link service to entity
            self.brain_graph_service.link(
                from_node=service_node.id,
                to_node=entity_node.id,
                edge_type="targets",
                initial_weight=0.6
            )


# Global processor instance - initialized by main.py
_processor: Optional[EventProcessor] = None


def get_processor() -> Optional[EventProcessor]:
    """Get the global event processor instance."""
    return _processor


def set_processor(processor: EventProcessor):
    """Set the global event processor instance."""
    global _processor
    _processor = processor
