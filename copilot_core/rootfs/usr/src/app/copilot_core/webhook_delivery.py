"""Worker-pool basierte Webhook-Zustellung.

Dieses Modul ersetzt das Thread-pro-Event Muster durch eine feste Anzahl
an Hintergrund-Workern und eine gemeinsame Queue.

PS-P0-009 Scope:
- DeliveryQueue-Grundgeruest mit start()/stop()/enqueue()
- konfigurierbare Workeranzahl, Queue-Groesse und Backpressure-Policy

PS-P0-012 Scope:
- Retry bei transienten Fehlern (Timeout/5xx/Netzwerk)
- kein Retry bei 4xx
- Exponential Backoff + Jitter

PS-P0-013 Scope:
- Graceful Shutdown mit Drain-Deadline
- oeffentliche Queue-Observability via get_stats()/stats
- Dokumentation der Betriebsparameter

PS-HEPH-023 Scope:
- Per-destination Concurrency Limit (DoS/Backpressure Guardrail)
- Per-destination Rate Limit (Token Bucket)
- globale Metriken fuer Wait/Timeout/RateLimit

Hinweis:
Die Default-Konfiguration arbeitet "single destination" (ein WebhookPusher
instanziert genau eine Queue pro URL). Die per-destination Optionen sind
abwaertskompatibel und erlauben spaeteres Multi-Destination Routing.
"""
from __future__ import annotations

import logging
import queue
import random
import threading
import time
import urllib.error
from typing import Any, Callable, Dict, Optional

_LOGGER = logging.getLogger(__name__)

Envelope = Dict[str, Any]
SendFunc = Callable[[Envelope], None]
DestinationKeyFunc = Callable[[Envelope], str]


class _TokenBucket:
    """Minimaler Token-Bucket (stdlib only) fuer per-destination Rate Limiting."""

    def __init__(self, rate_per_second: float, burst: int, now: float) -> None:
        self.rate_per_second = float(rate_per_second)
        self.capacity = float(burst)
        self.tokens = float(burst)
        self.updated_at = float(now)

    def _refill(self, now: float) -> None:
        if now <= self.updated_at:
            return
        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)
        self.updated_at = now

    def required_wait_seconds(self, amount: float, now: float) -> float:
        """Berechnet, wie lange bis amount Tokens verfuegbar sind.

        Returns:
            0.0 wenn sofort konsumierbar, sonst wait seconds > 0.
        """
        self._refill(now)
        if self.tokens >= amount:
            return 0.0
        missing = amount - self.tokens
        if self.rate_per_second <= 0:
            return float("inf")
        return missing / self.rate_per_second

    def consume(self, amount: float) -> None:
        if self.tokens < amount:
            raise RuntimeError("token bucket underflow")
        self.tokens -= amount


class WebhookDeliveryQueue:
    """Feste Worker-Queue fuer nicht-blockierende Webhook-Zustellung.

    Betriebsparameter:
    - worker_count: Anzahl gleichzeitiger Zustell-Worker.
    - max_queue_size: Maximale Anzahl gepufferter Envelopes.
    - backpressure_policy: Verhalten bei voller Queue
      (drop_newest | drop_oldest | block_timeout).
    - block_timeout_seconds: Blockierdauer fuer block_timeout.
    - max_retries: Retry-Budget pro Envelope bei transienten Fehlern.
    - retry_base_delay_seconds: Startwert fuer Exponential Backoff.
    - retry_max_delay_seconds: Obergrenze fuer Backoff.
    - retry_jitter_seconds: zusaetzlicher Zufallsanteil fuer Entkopplung.
    - delivery_deadline_seconds: Harte Obergrenze fuer die Gesamtdauer inkl. Backoff.

    PS-HEPH-023:
    - destination_key_func: Envelope -> Destination Key (z.B. URL oder Host).
    - destination_max_concurrency: Parallelitaet pro Destination (Semaphore).
    - destination_rate_limit_per_second: Rate pro Destination (Token Bucket).
    - destination_rate_limit_burst: Burst-Kapazitaet pro Destination.
    """

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
        max_retries: int = 2,
        retry_base_delay_seconds: float = 0.2,
        retry_max_delay_seconds: float = 5.0,
        retry_jitter_seconds: float = 0.1,
        delivery_deadline_seconds: Optional[float] = 60.0,
        destination_key_func: Optional[DestinationKeyFunc] = None,
        destination_max_concurrency: Optional[int] = None,
        destination_rate_limit_per_second: Optional[float] = None,
        destination_rate_limit_burst: int = 1,
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
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_base_delay_seconds < 0:
            raise ValueError("retry_base_delay_seconds must be >= 0")
        if retry_max_delay_seconds < 0:
            raise ValueError("retry_max_delay_seconds must be >= 0")
        if retry_jitter_seconds < 0:
            raise ValueError("retry_jitter_seconds must be >= 0")
        if delivery_deadline_seconds is not None and delivery_deadline_seconds < 0:
            raise ValueError("delivery_deadline_seconds must be >= 0 or None")

        if destination_max_concurrency is not None and destination_max_concurrency <= 0:
            raise ValueError("destination_max_concurrency must be > 0 or None")

        if destination_rate_limit_per_second is not None:
            if destination_rate_limit_per_second <= 0:
                raise ValueError("destination_rate_limit_per_second must be > 0 or None")
            if destination_rate_limit_burst <= 0:
                raise ValueError("destination_rate_limit_burst must be > 0")

        self._send_func = send_func
        self._worker_count = worker_count
        self._queue: queue.Queue[Envelope] = queue.Queue(maxsize=max_queue_size)
        self._backpressure_policy = backpressure_policy
        self._block_timeout_seconds = max(0.0, block_timeout_seconds)

        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds
        self._retry_jitter_seconds = retry_jitter_seconds
        self._delivery_deadline_seconds = delivery_deadline_seconds

        self._destination_key_func = destination_key_func
        self._destination_max_concurrency = destination_max_concurrency
        self._destination_rate_limit_per_second = destination_rate_limit_per_second
        self._destination_rate_limit_burst = destination_rate_limit_burst

        self._destination_lock = threading.Lock()
        self._destination_semaphores: dict[str, threading.Semaphore] = {}
        self._destination_buckets: dict[str, _TokenBucket] = {}

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
            "retry_total": 0,
            "deadline_exceeded_total": 0,
            # PS-HEPH-023
            "rate_limited_total": 0,
            "destination_concurrency_wait_total": 0,
            "destination_concurrency_timeout_total": 0,
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
        """Stoppt Worker; versucht vorher Queue bis zur Drain-Deadline zu drainen.

        Args:
            drain_timeout:
                - ``None``: unbegrenzt warten, bis alle enqueueten Aufgaben fertig sind.
                - ``0``: nicht auf Drain warten, Shutdown sofort fortsetzen.
                - ``>0``: maximal diese Sekunden auf Queue-Drain warten.
        """
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
                _LOGGER.warning(
                    "Delivery queue drain deadline reached with %d unfinished task(s)",
                    self._queue.unfinished_tasks,
                )
                break
            time.sleep(0.01)

        for worker in workers:
            if deadline is None:
                join_timeout = 0.2
            else:
                join_timeout = min(0.2, max(0.0, deadline - time.monotonic()))
            worker.join(timeout=join_timeout)

            if worker.is_alive():
                _LOGGER.warning("Delivery worker %s did not stop before deadline", worker.name)

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

    def get_stats(self) -> dict[str, int]:
        """Liefert einen thread-sicheren Snapshot der Delivery-Metriken."""
        snapshot = self._get_stats_snapshot()
        snapshot["queue_size"] = self._queue.qsize()

        with self._lock:
            workers = list(self._workers)
            started = self._started

        snapshot["worker_count"] = len(workers)
        snapshot["workers_alive"] = sum(1 for worker in workers if worker.is_alive())
        snapshot["started"] = int(started)
        return snapshot

    @property
    def stats(self) -> dict[str, int]:
        """Kurzform fuer get_stats()."""
        return self.get_stats()

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
            try:
                self._queue.get_nowait()
                self._queue.task_done()
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
                self._deliver_with_retry(envelope)
            except Exception as exc:  # noqa: BLE001
                # Safety fallback: sollte durch _deliver_with_retry bereits
                # abgefangen sein.
                _LOGGER.warning(
                    "Webhook delivery failed unexpectedly for %s: %s",
                    envelope.get("type"),
                    exc,
                )
            finally:
                self._queue.task_done()

    def _get_destination_key(self, envelope: Envelope) -> str:
        if self._destination_key_func is None:
            return "default"
        try:
            key = self._destination_key_func(envelope)
        except Exception:  # noqa: BLE001
            return "default"
        if not key:
            return "default"
        return str(key)

    def _get_destination_semaphore(self, destination_key: str) -> threading.Semaphore:
        if self._destination_max_concurrency is None:
            raise RuntimeError("destination semaphore requested but destination_max_concurrency is None")

        with self._destination_lock:
            sem = self._destination_semaphores.get(destination_key)
            if sem is None:
                sem = threading.Semaphore(self._destination_max_concurrency)
                self._destination_semaphores[destination_key] = sem
            return sem

    def _acquire_destination_slot(
        self,
        destination_key: str,
        deadline_at: Optional[float],
    ) -> Optional[threading.Semaphore]:
        if self._destination_max_concurrency is None:
            return None

        sem = self._get_destination_semaphore(destination_key)

        # Fast path: no wait.
        if sem.acquire(blocking=False):
            return sem

        self._increment_stat("destination_concurrency_wait_total")

        if deadline_at is None:
            sem.acquire()
            return sem

        remaining = max(0.0, deadline_at - time.monotonic())
        if remaining <= 0.0:
            self._increment_stat("destination_concurrency_timeout_total")
            return None

        acquired = sem.acquire(timeout=remaining)
        if not acquired:
            self._increment_stat("destination_concurrency_timeout_total")
            return None

        return sem

    def _get_destination_bucket(self, destination_key: str, now: float) -> _TokenBucket:
        if self._destination_rate_limit_per_second is None:
            raise RuntimeError("token bucket requested but destination_rate_limit_per_second is None")

        with self._destination_lock:
            bucket = self._destination_buckets.get(destination_key)
            if bucket is None:
                bucket = _TokenBucket(
                    rate_per_second=self._destination_rate_limit_per_second,
                    burst=self._destination_rate_limit_burst,
                    now=now,
                )
                self._destination_buckets[destination_key] = bucket
            return bucket

    def _wait_for_rate_limit(
        self,
        destination_key: str,
        deadline_at: Optional[float],
    ) -> bool:
        if self._destination_rate_limit_per_second is None:
            return True

        # Token bucket: wait until 1 token is available.
        while True:
            now = time.monotonic()
            bucket = self._get_destination_bucket(destination_key, now)

            with self._destination_lock:
                wait_seconds = bucket.required_wait_seconds(1.0, now)
                if wait_seconds <= 0.0:
                    bucket.consume(1.0)
                    return True

            if deadline_at is not None:
                remaining = deadline_at - now
                if remaining <= 0.0 or wait_seconds > remaining:
                    return False

            self._increment_stat("rate_limited_total")
            # Cap sleep to stay responsive to stop/drain deadlines.
            time.sleep(min(wait_seconds, 0.5))

    def _deliver_with_retry(self, envelope: Envelope) -> None:
        """Fuehrt Zustellung mit Fehlerklassifikation, Retry und Deadline durch."""
        retries_done = 0
        started_at = time.monotonic()

        deadline_at: Optional[float] = None
        if self._delivery_deadline_seconds is not None:
            deadline_at = started_at + max(0.0, self._delivery_deadline_seconds)

        destination_key = self._get_destination_key(envelope)

        while True:
            # Per-destination concurrency/rate-limit werden pro Attempt angewendet,
            # damit Retries/Backoff nicht dauerhaft Concurrency-Slots blockieren.
            sem: Optional[threading.Semaphore] = None
            try:
                sem = self._acquire_destination_slot(destination_key, deadline_at)
                if self._destination_max_concurrency is not None and sem is None:
                    self._increment_stat("failed_total")
                    self._increment_stat("deadline_exceeded_total")
                    _LOGGER.warning(
                        "Webhook delivery deadline exceeded while waiting for destination slot (%s)",
                        destination_key,
                    )
                    return

                allowed = self._wait_for_rate_limit(destination_key, deadline_at)
                if not allowed:
                    self._increment_stat("failed_total")
                    self._increment_stat("deadline_exceeded_total")
                    _LOGGER.warning(
                        "Webhook delivery deadline exceeded while rate-limited (%s)",
                        destination_key,
                    )
                    return

                self._send_func(envelope)
                self._increment_stat("delivered_total")
                return
            except Exception as exc:  # noqa: BLE001
                should_retry = self._is_transient_error(exc)
                if should_retry and retries_done < self._max_retries:
                    now = time.monotonic()
                    if deadline_at is not None:
                        remaining = deadline_at - now
                        if remaining <= 0:
                            self._increment_stat("failed_total")
                            self._increment_stat("deadline_exceeded_total")
                            _LOGGER.warning(
                                "Webhook delivery deadline exceeded for %s after %d attempt(s): %s",
                                envelope.get("type"),
                                retries_done + 1,
                                exc,
                            )
                            return

                    next_retry_number = retries_done + 1
                    backoff_seconds = self._compute_retry_delay_seconds(next_retry_number)

                    if deadline_at is not None:
                        now = time.monotonic()
                        remaining = deadline_at - now
                        if remaining <= 0 or backoff_seconds > remaining:
                            self._increment_stat("failed_total")
                            self._increment_stat("deadline_exceeded_total")
                            _LOGGER.warning(
                                "Webhook delivery deadline exceeded for %s after %d attempt(s): %s",
                                envelope.get("type"),
                                retries_done + 1,
                                exc,
                            )
                            return

                    retries_done = next_retry_number
                    self._increment_stat("retry_total")
                    _LOGGER.warning(
                        "Webhook delivery transient failure for %s: %s (retry %d/%d in %.3fs)",
                        envelope.get("type"),
                        exc,
                        retries_done,
                        self._max_retries,
                        backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    continue

                self._increment_stat("failed_total")
                _LOGGER.warning(
                    "Webhook delivery failed for %s after %d attempt(s): %s",
                    envelope.get("type"),
                    retries_done + 1,
                    exc,
                )
                return
            finally:
                if sem is not None:
                    sem.release()

    def _compute_retry_delay_seconds(self, retry_number: int) -> float:
        """Exponential Backoff + Jitter fuer den naechsten Retry."""
        exponential = self._retry_base_delay_seconds * (2 ** max(0, retry_number - 1))
        capped = min(exponential, self._retry_max_delay_seconds)
        jitter = random.uniform(0.0, self._retry_jitter_seconds)
        return capped + jitter

    @staticmethod
    def _is_transient_error(exc: Exception) -> bool:
        """Klassifiziert transiente Fehler (retrybar)."""
        if isinstance(exc, urllib.error.HTTPError):
            # 4xx -> fail-fast, 5xx -> transient
            return 500 <= int(exc.code) <= 599

        if isinstance(exc, urllib.error.URLError):
            return True

        if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
            return True

        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            if 500 <= status_code <= 599:
                return True
            if 400 <= status_code <= 499:
                return False

        return False
