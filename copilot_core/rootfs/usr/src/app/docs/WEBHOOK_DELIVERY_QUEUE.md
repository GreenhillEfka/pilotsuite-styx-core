# Webhook Delivery Queue (Betriebsparameter)

Die `WebhookDeliveryQueue` entkoppelt Event-Erzeugung von HTTP-POST-Zustellung und
arbeitet mit einem festen Worker-Pool statt Thread-pro-Event.

## Konfigurierbare Parameter

- `worker_count` (Default: `2`)
  - Anzahl paralleler Worker-Threads fuer ausgehende Zustellungen.
- `max_queue_size` (Default: `256`)
  - Maximale Anzahl gepufferter Webhook-Envelopes.
- `backpressure_policy` (Default: `drop_newest`)
  - Verhalten bei voller Queue:
    - `drop_newest`: neues Event verwerfen
    - `drop_oldest`: aeltestes Event verwerfen, neues aufnehmen
    - `block_timeout`: kurz blockieren, danach ggf. verwerfen
- `block_timeout_seconds` (Default: `0.1`)
  - Nur fuer `block_timeout`: max. Wartezeit beim Enqueue.
- `max_retries` (Default: `2`)
  - Retry-Budget pro Envelope fuer transiente Fehler.
- `retry_base_delay_seconds` (Default: `0.2`)
  - Initiale Backoff-Verzoegerung.
- `retry_max_delay_seconds` (Default: `5.0`)
  - Obere Backoff-Grenze.
- `retry_jitter_seconds` (Default: `0.1`)
  - Zufaelliger Zusatz zur Lastverteilung bei gleichzeitigen Retries.
- `delivery_deadline_seconds` (Default: `60.0`)
  - Harte Obergrenze fuer die Gesamtdauer einer Zustellung inkl. Backoff (Retry-Kette).
  - `None` deaktiviert die Deadline.

## WebhookPusher: Timeout & Payload Limits

Zusaetzlich erzwingt `WebhookPusher`:

- `request_timeout_seconds` (Default: `10.0`)
  - Socket-Timeout fuer `urllib.request.urlopen(...)`.
- `max_payload_bytes` (Default: `65536`)
  - Maximale Groesse des serialisierten Envelopes (UTF-8). Bei Ueberschreitung wird
    das Envelope vor `enqueue()` verworfen; Zaehler: `payload_oversize_total`.

## Shutdown-Verhalten

`stop(drain_timeout=...)` unterstuetzt eine definierte Drain-Deadline:

- `drain_timeout=None`: unbegrenzt warten, bis alle enqueueten Jobs verarbeitet sind.
- `drain_timeout=0`: sofortiger Shutdown ohne Drain-Wartezeit.
- `drain_timeout>0`: maximal diese Zeit auf Queue-Drain warten.

Wenn die Deadline erreicht wird, wird ein Warning geloggt und der Shutdown mit
best effort fortgesetzt.

## Observability

Folgende Metriken stehen ueber `get_stats()` bzw. `stats` zur Verfuegung:

- `enqueued_total`
- `dropped_total`
- `delivered_total`
- `failed_total`
- `retry_total`
- `deadline_exceeded_total`
- `queue_size`
- `worker_count`
- `workers_alive`
- `started` (0/1)
