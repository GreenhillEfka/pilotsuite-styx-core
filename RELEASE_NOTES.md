# Release Notes v13.7.0 -- Musikwolke HA-Integration & Documentation Overhaul

**Datum:** 2026-03-11
**Branch:** main
**Tag:** `v13.7.0`
**HA hassfest:** compliant
**Paired Release:** Core v13.7.0 <-> HA v13.7.0

---

## Ueberblick

PilotSuite v13.7.0 schliesst die End-to-End-Musikwolke-Integration ab. Die HA-Integration steuert jetzt alle Musikwolke-Endpunkte ueber 8 neue Services an.

### Core API-Endpunkte (jetzt voll HA-integriert)

| API Pfad | HA Service |
|----------|-----------|
| `POST /api/v1/musikwolke/create` | `copilot_ha.musikwolke_create` |
| `POST /api/v1/musikwolke/dissolve` | `copilot_ha.musikwolke_dissolve` |
| `POST /api/v1/musikwolke/volume/<zone_id>` | `copilot_ha.musikwolke_volume` |
| `POST /api/v1/media/zones/<id>/play` | `copilot_ha.musikwolke_play` |
| `POST /api/v1/media/zones/<id>/pause` | `copilot_ha.musikwolke_pause` |
| `POST /api/v1/media/musikwolke/start` | `copilot_ha.musikwolke_start_follow` |
| `POST /api/v1/media/musikwolke/<id>/stop` | `copilot_ha.musikwolke_stop_follow` |
| `POST /api/v1/zone-automation/zones/<id>/mode` | `copilot_ha.zone_automation_set_mode` |

---

## Dokumentation

| Dokument | Beschreibung |
|----------|-------------|
| `docs/HANDBUCH.md` | Deutsches Benutzerhandbuch |
| `docs/INSTALLATIONSANLEITUNG.md` | Installationsanleitung |

---

## Upgrade-Hinweise

- **Breaking Changes:** Keine
- **Migration:** `ha addons update pilotsuite_core`

---

**PilotSuite v13.7.0** -- Local-first, Privacy-first, Governance-first.
