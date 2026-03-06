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

## PS-HEPH-023: Per-Destination Limits (DoS/Backpressure)

Die Queue kann optional pro "Destination" limitieren. Das ist abwaertskompatibel
und in der Default-Integration (ein `WebhookPusher` pro URL) praktisch eine
Safety-Rail fuer spaetere Multi-Destination Erweiterungen.

- `destination_key_func` (Default: `None`)
  - Callable `envelope -> str`, das die Destination bestimmt (z. B. URL, Host,
    Tenant-Key).
  - Falls `None`, nutzt die Queue den Key `"default"`.

- `destination_max_concurrency` (Default: `None`)
  - Wenn gesetzt: max. gleichzeitige In-Flight Zustellungen pro Destination.
  - Implementiert via Semaphore pro Destination.
  - Retries/Backoff halten keinen Slot dauerhaft: pro Attempt wird neu acquired.

- `destination_rate_limit_per_second` (Default: `None`)
  - Wenn gesetzt: Token-Bucket Rate pro Destination.

- `destination_rate_limit_burst` (Default: `1`)
  - Burst-Kapazitaet fuer den Token-Bucket.

## WebhookPusher: Per-Destination Caps (Config/Env Wiring)

Die Caps werden jetzt direkt ueber `WebhookPusher` konfigurierbar und an die
`WebhookDeliveryQueue` weitergereicht. Prioritaet: **Config-Werte** (z. B.
`configuration.yaml`/Dict) haben Vorrang, **Env** dient als Fallback.

Config Keys (alle optional; Werte > 0 erforderlich, ansonsten Validation-Error der Queue):
- `webhook_destination_max_concurrency` (int|None)
- `webhook_destination_rate_limit_per_second` (float|None)
- `webhook_destination_rate_limit_burst` (int, default: `1`)

Env-Fallbacks:
- `PILOTSUITE_WEBHOOK_DESTINATION_MAX_CONCURRENCY`
- `PILOTSUITE_WEBHOOK_DESTINATION_RATE_LIMIT_PER_SECOND`
- `PILOTSUITE_WEBHOOK_DESTINATION_RATE_LIMIT_BURST`

Verhalten:
- `max_concurrency=None`/nicht gesetzt → kein per-destination Semaphore.
- `rate_limit_per_second=None`/nicht gesetzt → kein Token-Bucket; Burst wird ignoriert.
- `rate_limit_burst` muss > 0 sein, wenn Rate-Limit gesetzt ist (default 1).

## WebhookPusher: Timeout & Payload Limits

Zusaetzlich erzwingt `WebhookPusher`:

- `request_timeout_seconds` (Default: `10.0`)
  - Socket-Timeout fuer `urllib.request.urlopen(...)`.
- `max_payload_bytes` (Default: `65536`)
  - Maximale Groesse des serialisierten Envelopes (UTF-8). Bei Ueberschreitung wird
    das Envelope vor `enqueue()` verworfen; Zaehler: `payload_oversize_total`.

## WebhookPusher: Destination Policy / URL Validation (SSRF Guardrails)

Beim Initialisieren validiert `WebhookPusher` die konfigurierte `webhook_url`, um
triviale SSRF-/Scheme-Footguns zu vermeiden (``urllib`` kann je nach Scheme auch
lokale Ressourcen oeffnen).

Enforced Guardrails:
- nur `http`/`https` erlaubt (kein `file://`, `ftp://`, ...)
- URL muss absolut sein und einen Host enthalten
- keine URL-Credentials (`user:pass@host`)
- kein URL-Fragment (`#...`)

Default wird eine `destination_policy` genutzt (aus Env gebaut), die typische
SSRF-Ziele blockt: private/loopback/link-local IP-Ranges sowie bekannte
Cloud-Metadata-Endpoints.

Env-Toggles (Default: konservativ):
- `PILOTSUITE_WEBHOOK_DESTINATION_ALLOW_PRIVATE=true`
  - erlaubt loopback + private Ranges (RFC1918/ULA/CGNAT). Link-local/Metadata
    bleiben weiterhin geblockt.
- `PILOTSUITE_WEBHOOK_DESTINATION_RESOLVE_DNS=true`
  - optionaler DNS-Resolve-Check fuer Hostnames; fail-closed bei Resolve-Fehler.
- `PILOTSUITE_WEBHOOK_DESTINATION_ALLOWED_DOMAINS=...` (CSV; unterstützt `*.example.com`)
  - wenn gesetzt, muss der Host matchen.
- `PILOTSUITE_WEBHOOK_DESTINATION_BLOCKED_DOMAINS=...` (CSV; unterstützt `*.example.com`)
  - wenn gesetzt, wird bei Match geblockt.

Optional kann weiterhin eine eigene `destination_policy` (Callable) uebergeben werden:
- `destination_policy(url) -> bool`
- `False` fuehrt zu `ValueError` und verhindert die Initialisierung

## WebhookPusher: Optionales HMAC-Signing + Replay-Schutz (PS-HEPH-024)

Wenn `webhook_signing_secret` gesetzt ist, werden bei jedem ausgehenden Webhook-POST
folgende Header gesendet:

- `X-Webhook-Timestamp` (z. B. `1710000000`)
- `X-Webhook-Nonce` (zufaelliger UUID4 Hex-String)
- `X-Webhook-Signature` mit Schema `sha256=<hexdigest>`

Signatur-Basis auf Core-Seite:

- `body = json.dumps(envelope, default=str).encode("utf-8")`
- `timestamp = str(int(time.time()))`
- `nonce = uuid.uuid4().hex`
- `signing_input = f"{timestamp}.{nonce}.".encode("utf-8") + body`
- `signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()`

Der HA/Consumer-Vertrag sollte mindestens folgende Checks implementieren:

- Timestamp-Skala darf nicht älter/frueher als
  `webhook_signing_timestamp_ttl_seconds` sein (`abs(now - int(timestamp)) <= ttl`).
- Nonce pro Endpoint/Token gegen Replay in einem kurzzeitigen Cache nachweisen.
- Signatur mit `hmac.compare_digest` gegen erneut berechnete Signatur validieren.
- Bei Verifikationsfehler: `401 invalid_signature`/`unauthorized`-Response.

Core-Konfigurations-Optionen (Core-Seite):

- `webhook_signing_secret` (String, optional)
  - leer/`None` => Signieren deaktiviert.
- `webhook_signing_timestamp_ttl_seconds` (Default: `300`)
  - Wert wird aktuell auf dem Core validiert und fuer den Verifikationsvertrag mitgegeben.

## Shutdown-Verhalten

`stop(drain_timeout=...)` unterstuetzt eine definierte Drain-Deadline:

- `drain_timeout=None`: unbegrenzt warten, bis alle enqueueten Jobs verarbeitet sind.
- `drain_timeout=0`: sofortiger Shutdown ohne Drain-Wartezeit.
- `drain_timeout>0`: maximal diese Zeit auf Queue-Drain warten.

Wenn die Deadline erreicht wird, wird ein Warning geloggt und der Shutdown mit
best effort fortgesetzt.

## Observability

Folgende Metriken stehen ueber `get_stats()` bzw. `stats` zur Verfuegung:

Queue-Core:
- `enqueued_total`
- `dropped_total`
- `delivered_total`
- `failed_total`
- `retry_total`
- `deadline_exceeded_total`
- `rate_limited_total` (PS-HEPH-023)
- `destination_concurrency_wait_total` (PS-HEPH-023)
- `destination_concurrency_timeout_total` (PS-HEPH-023)
- `queue_size`
- `worker_count`
- `workers_alive`
- `started` (0/1)

Pusher-zusaetzlich:
- `payload_oversize_total`
- `destination_rejected_total`
