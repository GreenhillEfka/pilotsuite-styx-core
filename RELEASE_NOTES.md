# PilotSuite Core — Release Notes v15.0.3

**Datum:** 2026-03-21
**Version:** 15.0.3
**Gepaart mit:** HA v15.0.1

---

## In Kuerze

v15.0.3 ist der saubere Core-Release fuer den bereits auf `main` gelandeten Zone-Sync-/Contract-Fix. Der Core kann jetzt HA-Zonendefinitionen ueber `/api/v1/zone-automation/sync-definitions` annehmen; zugleich sind die Release-Metadaten wieder konsistent statt zwischen 15.0.1/15.0.2/15.0.0 zu driften.

**Paired mit:** Home Assistant Add-on v15.0.1

---

## Was ist neu

### Zone Presence — Bidirektionale Hold-Steuerung

- **Hold API**: `POST /api/v1/presence/zone/presence/<zone_id>/hold` — HA kann Core ueber Presence-Status informieren
- **State API**: `POST /api/v1/presence/zone/presence/<zone_id>/state` — aggregierte Presence an Core Neurons
- **Legacy Aliases**: Alte API-Pfade bleiben funktional

### Zone Proposals — Automatische Zone-Entdeckung

- `GET/POST /zone-proposals` — neue Proposals abrufen und evaluieren
- `POST /zone-proposals/accept` — Proposal mit Modul-Policy akzeptieren
- **Confidence + Lift**: Automatische Scorings zeigenraeumen wie sicher ein Vorschlag ist

### Presence v3.4 — Praezisere Anwesenheit

- **Multi-Source Aggregation**: any-on Regel mit hold/override und sources-Tracking
- **Numeric Bucketing**: Lux→dark/bright, Temp→cold/warm
- **ZoneBased Miner**: Semantic bucketing fuer automatische Korrelationserkennung

### Zone-Editor — Moderne CRUD-API

- `/api/v1/zone-editor` — vollstaendige Zone-CRUD mit Domain, Rooms, Entity-Count

---

## Kompatibilitaet

| Komponente | Version |
|---|---|
| PilotSuite Core | **15.0.3** |
| PilotSuite HA Add-on | **15.0.1** (Paired) |
| Home Assistant | **2024.4.0+** |
| Python | **3.11+** |

---

## VISION-Bezug

PilotSuite Vision (v14.6.5):

> "Das Haus soll sich Ihnen anpassen — nicht Sie sich Ihrem Zuhause."

- **Lebenslanger Begleiter:** Zone Miner lernt automatisch neue Zonen
- **Governance-first:** Hold = Nutzer entscheidet, System setzt um
- **Privacy-first:** Alles lokal. Kein Cloud.
- **Erklaerbar:** Zone-Proposals mit Confidence + Lift, Rueckverfolgbarkeit

---

## Getestet

| Check | Ergebnis |
|---|---|
| API Tests | ✅ |
| Zone-Editor CRUD | ✅ |
| Presence Hold API | ✅ |
| Zone-Proposals Pipeline | ✅ |

---

*PilotSuite Core v15.0.3 — Lokal. Lernend. Lebenslang.*
