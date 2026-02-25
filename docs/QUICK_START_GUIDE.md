# PilotSuite Quick Start

Stand: **v8.11.0**

## Zielbild

`Home Assistant` ↔ `PilotSuite HA Integration` ↔ `PilotSuite Core Add-on (:8909)`

## 5-Minuten Setup

1. Core-Repo als Add-on-Quelle eintragen:
   - `https://github.com/GreenhillEfka/pilotsuite-styx-core`
2. Add-on **PilotSuite Core** installieren und starten
3. Health prüfen:

```bash
curl -sS http://<HA-IP>:8909/health
```

4. HACS-Integration installieren:
   - `https://github.com/GreenhillEfka/pilotsuite-styx-ha`
5. Integration `PilotSuite - Styx` in HA hinzufügen (Zero Config empfohlen)

## Modell-Defaults

- Lokal: `qwen3:0.6b`
- Cloud fallback: `qwen3.5:cloud` auf `https://ollama.com/v1`

## Minimale Runtime-Prüfung

```bash
curl -sS http://<HA-IP>:8909/chat/status
curl -sS http://<HA-IP>:8909/api/v1/status
```

## Häufige Fehler

- `Restart required` in HACS: HA neu starten.
- Chat antwortet nicht: Modell/Provider-Konfiguration im Add-on prüfen.
- `401/403`: Token in HA-Integration und Core identisch setzen.

## Weiterführend

- Add-on Info-Screen: `copilot_core/DOCS.md`
- HA Setup: `pilotsuite-styx-ha/SETUP.md`
