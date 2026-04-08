"""
Event processing pipeline connecting EventStore to BrainGraphService.

This module provides automatic processing of ingested events to update
the brain graph with real-time smart home state and relationships.
"""

import logging
import threading
from typing import Dict, Any, Optional, Callable, List, Set
from ..brain_graph.service import BrainGraphService
from ..dev_surface.service import dev_surface

logger = logging.getLogger(__name__)


class EventProcessor:
    """
    Processes events from EventStore and forwards them to downstream services.

    Currently supports:
    - BrainGraphService integration for knowledge graph updates
    - Configurable event filters and processors
    - Rollback on batch failure (only commits successfully processed events)
    - Idempotency via event ID deduplication
    """

    def __init__(self, brain_graph_service: Optional[BrainGraphService] = None):
        self.brain_graph_service = brain_graph_service
        self.processors: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()
        # Idempotency: track recently processed event IDs
        self._processed_ids: Set[str] = set()
        self._max_processed_ids = 10000

        # Register default processors
        if brain_graph_service:
            self.processors.append(self._process_for_brain_graph)

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

        return stats

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
        zone_id = event.get("zone_id")

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
        domain = event.get("domain", "")
        service = event.get("service", "")
        entity_id = event.get("entity_id", "")

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

        # Link to target entity if specified
        if entity_id:
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
