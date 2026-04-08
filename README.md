# PilotSuite Core — Home Assistant Add-on

**Version:** 20.0.0  
**License:** MIT  
**Author:** GreenhillEfka

## Overview

PilotSuite Core ist der aktuelle `v20.0.0`-Runtime-Baum des Add-ons.
Der gelandete Scope ist derzeit bewusst schmal: Health-Endpoint, `/version`, read-only `/api/v1/presence`, read-only `/api/v1/analytics`, Notification-Feed unter `GET /api/v1/notifications`, minimaler Root-Create-Alias unter `POST /api/v1/notifications` mit historischer `data`-/`channel`-Payload-Kompatibilität, zusätzlicher Alias-Write auf `/api/v1/notifications/send` mit demselben kompatiblen Minimal-Scope, read-only `/api/v1/notifications/digest`, read-only `/api/v1/notifications/pending`, read-only `/api/v1/notifications/stats`, minimaler Dismiss-Write auf `/api/v1/notifications/{notification_id}`, minimaler Read-Ack auf `/api/v1/notifications/{notification_id}/read`, minimaler Subscription-Add auf `/api/v1/notifications/subscribe`, read-only `/api/v1/notifications/subscriptions`, minimaler Single-Device-Write auf `/api/v1/notifications/subscriptions/{device_id}`, minimaler Subscription-Remove auf `/api/v1/notifications/unsubscribe`, read-only `/api/v1/zones`, plus `widget_positions`-API mit lokaler Persistenz.
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
| `/api/v1/notifications` | GET, POST | Read-only Notification-Feed plus minimaler Root-Create-Alias mit Read-after-write-Konsistenz und historischer `data`-/`channel`-Payload-Kompatibilität ohne Delivery-Reintro |
| `/api/v1/notifications/send` | POST | Minimaler Notification-Create-Write für genau eine API-Notification mit Read-after-write-Konsistenz und demselben historischen `data`-/`channel`-Kompatibilitätsscope |
| `/api/v1/notifications/digest` | GET | Read-only Notification-Digest als kleinster Summary-Follow-up-Slice aus dem historischen `v20`-Contract |
| `/api/v1/notifications/pending` | GET | Read-only Pending-Queue als kleinster Delivery-Follow-up-Slice aus dem historischen `v20`-Contract |
| `/api/v1/notifications/stats` | GET | Read-only Notification-Statistik als kleinster Metrics-Follow-up-Slice aus dem historischen `v20`-Contract |
| `/api/v1/notifications/{notification_id}` | DELETE | Minimaler Dismiss-Write für genau eine bestehende Notification-ID, der Feed- und Digest-Sicht synchron hält |
| `/api/v1/notifications/{notification_id}/read` | POST | Minimaler Read-Ack für genau eine bestehende Notification-ID, der Feed-, Digest- und Stats-Sicht synchron hält |
| `/api/v1/notifications/subscribe` | POST | Minimaler Subscription-Add bzw. Re-Register eines Device-Snapshots über `device_id`, der bekannte Devices wieder aktiviert |
| `/api/v1/notifications/subscriptions` | GET | Read-only Device-Subscription-Snapshot als kleinster Subscription-Follow-up-Slice aus dem historischen `v20`-Contract |
| `/api/v1/notifications/subscriptions/{device_id}` | PUT | Minimales Update für `enabled` und bekannte Preference-Flags eines bestehenden Subscription-Devices |
| `/api/v1/notifications/unsubscribe` | POST | Minimaler Remove eines bestehenden Subscription-Devices über `device_id` |
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
- ✅ **Notifications Feed** — `GET /api/v1/notifications` liefert den kleinsten read-only Feed aus dem historischen `v20`-Notifications-Contract
- ✅ **Notifications Root Create Alias** — `POST /api/v1/notifications` nutzt bewusst denselben minimalen API-Write-Scope wie der Send-Pfad, akzeptiert zusätzlich historische `data`- und `channel`-Payload-Hints und hält Feed-, Digest- und Stats-Sicht per Read-after-write synchron
- ✅ **Notifications Send** — `/api/v1/notifications/send` erzeugt minimal genau eine API-Notification, teilt denselben `data`-/`channel`-Kompatibilitätsscope und bleibt als expliziter Alias-Write öffentlich
- ✅ **Notifications Digest** — `/api/v1/notifications/digest` liefert den kleinsten read-only Summary-Follow-up-Slice auf Basis desselben historischen Notifications-Bestands
- ✅ **Notifications Pending Queue** — `/api/v1/notifications/pending` liefert den kleinsten read-only Delivery-Follow-up-Slice für noch ausstehende Zustellungen
- ✅ **Notifications Stats** — `/api/v1/notifications/stats` liefert den kleinsten read-only Statistik-Slice auf Basis desselben historischen Notifications-Bestands
- ✅ **Notifications Dismiss** — `/api/v1/notifications/{notification_id}` markiert minimal genau eine bestehende Notification als dismissed und hält Feed- und Digest-Sicht per Read-after-write synchron
- ✅ **Notifications Mark Read** — `/api/v1/notifications/{notification_id}/read` quittiert minimal genau eine bestehende Notification als gelesen und hält Feed-, Digest- und Stats-Sicht per Read-after-write synchron
- ✅ **Notifications Subscribe** — `/api/v1/notifications/subscribe` legt minimal neue Device-Subscriptions an, aktualisiert bekannte Devices und aktiviert Re-Registers wieder ohne größere Manager-, Register- oder HA-Surface wieder einzuführen
- ✅ **Notifications Subscriptions** — `/api/v1/notifications/subscriptions` liefert den kleinsten read-only Device-Subscription-Snapshot aus demselben historischen Notifications-Contract
- ✅ **Notifications Subscription Update** — `/api/v1/notifications/subscriptions/{device_id}` aktualisiert minimal `enabled` und bekannte Preference-Flags für bestehende Geräte, ohne Subscribe-, Register- oder Manager-Surface mitzuziehen
- ✅ **Notifications Unsubscribe** — `/api/v1/notifications/unsubscribe` entfernt minimal bestehende Geräte-Subscriptions per `device_id`, ohne die größere Subscribe-/HA-Registration-Surface wieder einzuführen
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
