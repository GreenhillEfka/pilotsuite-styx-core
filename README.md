# PilotSuite Core — Home Assistant Add-on

**Version:** 20.0.0  
**License:** MIT  
**Author:** GreenhillEfka

## Overview

PilotSuite Core ist der aktuelle `v20.0.0`-Runtime-Baum des Add-ons.
Der gelandete Scope ist derzeit bewusst schmal: Health-Endpoint, `/version`, read-only `/api/v1/presence`, read-only `/api/v1/analytics`, read-only `/api/v1/notifications`, read-only `/api/v1/notifications/digest`, read-only `/api/v1/notifications/pending`, read-only `/api/v1/notifications/stats`, read-only `/api/v1/zones`, plus `widget_positions`-API mit lokaler Persistenz.
Frühere Legacy-Endpunkte werden in diesem Worktree erst wieder öffentlich geführt, wenn sie gegen die echte Runtime neu gelandet sind.

## Architecture

```
┌─────────────────────────────────────┐
│  Home Assistant (HACS Integration)  │
│  - Entities, Sensors, Cards         │
│  - User Interface                   │
└──────────────┬──────────────────────┘
               │ HTTP API (Port 8909)
               ▼
┌─────────────────────────────────────┐
│  PilotSuite Core (This Add-on)      │
│  - Brain Architecture               │
│  - Neural Sensors                   │
│  - ML/AI Processing                 │
│  - API Server                       │
└─────────────────────────────────────┘
```

## Installation

### Via Add-on Store

1. Add repository: `https://github.com/GreenhillEfka/pilotsuite-styx-core`
2. Install "PilotSuite Core"
3. Configure (host, port, API keys)
4. Start the add-on

### Configuration

```yaml
log_level: info          # critical|error|warning|info|debug
ollama_host: localhost   # Ollama server host
ollama_port: 11434       # Ollama server port
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/version` | GET | Laufende Core-Version aus dem Runtime-Manifest |
| `/api/v1/presence` | GET | Read-only Haushalts-Presence-Zusammenfassung auf Basis des historischen `v20`-Contracts |
| `/api/v1/analytics` | GET | Read-only Analytics-Übersicht als kleinster öffentlicher Root-Slice aus dem historischen `v20`-Bestand |
| `/api/v1/notifications` | GET | Read-only Notification-Feed als kleinster öffentlicher Root-Slice aus dem historischen `v20`-Contract |
| `/api/v1/notifications/digest` | GET | Read-only Notification-Digest als kleinster Summary-Follow-up-Slice aus dem historischen `v20`-Contract |
| `/api/v1/notifications/pending` | GET | Read-only Pending-Queue als kleinster Delivery-Follow-up-Slice aus dem historischen `v20`-Contract |
| `/api/v1/notifications/stats` | GET | Read-only Notification-Statistik als kleinster Metrics-Follow-up-Slice aus dem historischen `v20`-Contract |
| `/api/v1/zones` | GET | Read-only Habitus-Zonenkatalog aus dem historischen `v20`-Bestand |
| `/api/v1/widgets/positions` | GET, POST | Liste aller Widget-Positionen, Einzelposition speichern |
| `/api/v1/widgets/positions/bulk` | POST | Mehrere Widget-Positionen gesammelt speichern |
| `/api/v1/widgets/positions/{widget_id}` | GET, DELETE | Einzelposition lesen oder löschen |
| `/api/v1/widgets/positions/{widget_id}/history` | POST | Aktuelle Position in die Historie schreiben |
| `/api/v1/widgets/positions/{widget_id}/undo` | POST | Letzte Positionsänderung rückgängig machen |
| `/api/v1/widgets/positions/{widget_id}/redo` | POST | Letzte Rücknahme erneut anwenden |
| `/api/v1/widgets/positions/reset` | POST | Alle Widget-Positionen zurücksetzen |

Full API documentation: `docs/openapi.yaml` and `docs/openapi.json`

Nicht Teil der aktuellen `v20`-Runtime bleiben weiterhin nur nicht inventarisierte Legacy-Endpunkte außerhalb der hier dokumentierten Surface.

## Current Runtime Scope

- ✅ **Health Endpoint** — einfacher Runtime-Liveness-Check über `/health`
- ✅ **Version Endpoint** — `/version` liest die gelandete Core-Version direkt aus dem Runtime-Manifest `VERSION`
- ✅ **Presence Summary** — `/api/v1/presence` liefert den kleinsten read-only Haushaltsstatus aus dem historischen `v20`-Presence-Contract
- ✅ **Analytics Overview** — `/api/v1/analytics` liefert den kleinsten read-only Root-Überblick aus dem historischen `v20`-Analytics-Bestand
- ✅ **Notifications Feed** — `/api/v1/notifications` liefert den kleinsten read-only Feed aus dem historischen `v20`-Notifications-Contract
- ✅ **Notifications Digest** — `/api/v1/notifications/digest` liefert den kleinsten read-only Summary-Follow-up-Slice auf Basis desselben historischen Notifications-Bestands
- ✅ **Notifications Pending Queue** — `/api/v1/notifications/pending` liefert den kleinsten read-only Delivery-Follow-up-Slice für noch ausstehende Zustellungen
- ✅ **Notifications Stats** — `/api/v1/notifications/stats` liefert den kleinsten read-only Statistik-Slice auf Basis desselben historischen Notifications-Bestands
- ✅ **Zones Catalog** — `/api/v1/zones` liefert den kleinsten read-only Habitus-Zonenkatalog aus dem historischen `v20`-Bestand
- ✅ **Widget Positions API** — CRUD, Bulk, History, Undo, Redo und Reset unter `/api/v1/widgets/positions*`
- ✅ **Contract/OpenAPI-Inventur** — `docs/openapi.*` und Guard gegen Runtime-Drift
- ✅ **Dateibasierte Persistenz** — Widget-Layouts werden lokal in `dashboard/data/widget_positions.json` gehalten

## Requirements

- Home Assistant ≥ 2024.1.0
- Ollama server (optional, for local LLM)
- 2GB RAM minimum
- Docker support

## Support

- Issues: https://github.com/GreenhillEfka/pilotsuite-styx-core/issues
- Discord: PilotSuite Community
- Documentation: https://docs.pilotsuite.ai

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

**Built with ❤️ by the PilotSuite Team**
