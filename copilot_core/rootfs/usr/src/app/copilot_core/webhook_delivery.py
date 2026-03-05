"""Worker-pool basierte Webhook-Zustellung.

Dieses Modul ersetzt das Thread-pro-Event Muster durch eine feste Anzahl
an Hintergrund-Workern und eine gemeinsame Queue.

PS-P0-009 Scope:
- DeliveryQueue-Grundgeruest mit start()/stop()/enqueue()
- konfigurierbare Workeranzahl, Queue-Groesse und Backpressure-Policy
- Single-Attempt Versand (noch ohne Retry-Logik)
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional

_LOGGER = logging.getLogger(__name__)

Envelope = Dict[str, Any]
SendFunc = Callable[[Envelope], None]


class WebhookDeliveryQueue:
    """Feste Worker-Queue fuer nicht-blockierende Webhook-Zustellung."""

    SUPPORTED_BACKPRESSURE_POLICIES = {
        "drop_oldest",
        "drop_newest",
        "block_timeout",
    }

    def __init__(
        self,
        send_func: SendFunc,
        worker_count: int = 2,
        max_queue_size: int = 256,
        backpressure_policy: str = "drop_newest",
        block_timeout_seconds: float = 0.1,
    ) -> None:
        if worker_count <= 0:
            raise ValueError("worker_count must be > 0")
        if max_queue_size <= 0:
            raise ValueError("max_queue_size must be > 0")
        if backpressure_policy not in self.SUPPORTED_BACKPRESSURE_POLICIES:
            raise ValueError(
                "unsupported backpressure_policy: "
                f"{backpressure_policy!r}; expected one of "
                f"{sorted(self.SUPPORTED_BACKPRESSURE_POLICIES)}"
            )

        self._send_func = send_func
        self._worker_count = worker_count
        self._queue: queue.Queue[Envelope] = queue.Queue(maxsize=max_queue_size)
        self._backpressure_policy = backpressure_policy
        self._block_timeout_seconds = max(0.0, block_timeout_seconds)

        self._workers: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._started = False

        self._stats_lock = threading.Lock()
        self._stats: dict[str, int] = {
            "enqueued_total": 0,
            "dropped_total": 0,
            "delivered_total": 0,
            "failed_total": 0,
        }

    def start(self) -> None:
        """Startet den festen Worker-Pool (idempotent)."""
        with self._lock:
            if self._started:
                return

            self._stop_event.clear()
            self._workers = []
            for idx in range(self._worker_count):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"webhook-delivery-{idx + 1}",
                    daemon=True,
                )
                worker.start()
                self._workers.append(worker)

            self._started = True

    def stop(self, drain_timeout: Optional[float] = 1.0) -> None:
        """Stoppt Worker; versucht vorher Queue bis zum Timeout zu drainen."""
        with self._lock:
            if not self._started:
                return
            self._stop_event.set()
            workers = list(self._workers)

        deadline: Optional[float] = None
        if drain_timeout is not None:
            deadline = time.monotonic() + max(0.0, drain_timeout)

        while self._queue.unfinished_tasks > 0:
            if deadline is not None and time.monotonic() >= deadline:
                break
            time.sleep(0.01)

        for worker in workers:
            worker.join(timeout=0.2)

        with self._lock:
            self._workers = []
            self._started = False

    def enqueue(self, envelope: Envelope) -> bool:
        """Fuegt ein Envelope in die Queue ein.

        Returns:
            True: Envelope wurde angenommen.
            False: Envelope wurde durch Backpressure verworfen.
        """
        if not self._started:
            self.start()

        if self._backpressure_policy == "drop_newest":
            return self._enqueue_drop_newest(envelope)
        if self._backpressure_policy == "drop_oldest":
            return self._enqueue_drop_oldest(envelope)
        return self._enqueue_block_timeout(envelope)

    def _increment_stat(self, stat_key: str, amount: int = 1) -> None:
        with self._stats_lock:
            self._stats[stat_key] += amount

    def _get_stats_snapshot(self) -> dict[str, int]:
        with self._stats_lock:
            return dict(self._stats)

    def _enqueue_drop_newest(self, envelope: Envelope) -> bool:
        try:
            self._queue.put_nowait(envelope)
            self._increment_stat("enqueued_total")
            return True
        except queue.Full:
            self._increment_stat("dropped_total")
            _LOGGER.warning("Delivery queue full; dropped newest webhook event")
            return False

    def _enqueue_drop_oldest(self, envelope: Envelope) -> bool:
        try:
            self._queue.put_nowait(envelope)
            self._increment_stat("enqueued_total")
            return True
        except queue.Full:
            dropped_oldest = False
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                dropped_oldest = True
                self._increment_stat("dropped_total")
            except queue.Empty:
                pass

            try:
                self._queue.put_nowait(envelope)
                self._increment_stat("enqueued_total")
                _LOGGER.warning("Delivery queue full; dropped oldest webhook event")
                return True
            except queue.Full:
                # Entweder nur das neue Event verworfen, oder (bei Race) zusaetzlich
                # zum bereits verworfenen oldest auch das aktuelle newest verloren.
                self._increment_stat("dropped_total")
                _LOGGER.warning("Delivery queue still full; dropped newest webhook event")
                return False

    def _enqueue_block_timeout(self, envelope: Envelope) -> bool:
        try:
            self._queue.put(envelope, timeout=self._block_timeout_seconds)
            self._increment_stat("enqueued_total")
            return True
        except queue.Full:
            self._increment_stat("dropped_total")
            _LOGGER.warning("Delivery queue full after block_timeout; dropped webhook event")
            return False

    def _worker_loop(self) -> None:
        while True:
            if self._stop_event.is_set() and self._queue.empty():
                return

            try:
                envelope = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                # PS-P0-009: Single attempt only (Retry kommt in PS-P0-012).
                self._send_func(envelope)
                self._increment_stat("delivered_total")
            except Exception as exc:  # noqa: BLE001
                self._increment_stat("failed_total")
                _LOGGER.warning(
                    "Webhook delivery failed for %s: %s",
                    envelope.get("type"),
                    exc,
                )
            finally:
                self._queue.task_done()
