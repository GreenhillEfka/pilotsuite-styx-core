# Release Notes v13.0.4 -- Module Registry, 100% Coverage & 3D Vision

**Datum:** 2026-03-03
**Branch:** main
**Tag:** `v13.0.4`
**HA hassfest:** ✓ compliant

---

## Ueberblick

PilotSuite v13.0.4 ist ein **Feature Release**, das folgende Highlights bringt:

- **Module Registry API**: Vollstaendige REST-API mit 100% Test-Coverage
- **Test Coverage 61%** (Kern-Module: 75-93%)
- **HA Integration 13.0.4**: Volle Sync mit Home Assistant Add-on Manifest
- **3D Vision Features**: Neue `vision3d.js` Komponente fuer erweiterte Visualisierung

---

## Highlights

### Module Registry API (100% Coverage)

Vollstaendige REST-API fuer das zentrale Modul-Registry-System:

**Endpoints**
- `GET /api/v1/modules` -- Alle Module auflisten
- `GET /api/v1/modules/<id>` -- Einzelnes Modul abrufen
- `POST /api/v1/modules` -- Neues Modul registrieren
- `PUT /api/v1/modules/<id>` -- Modul aktualisieren
- `DELETE /api/v1/modules/<id>` -- Modul entfernen
- `GET /api/v1/modules/status` -- Modul-Status abfragen

**Test Coverage**
- 100% Coverage fuer alle Registry-Funktionen
- Error-Path-Tests: fehlende Module, Invalid Data, etc.
- Fallback-to-Singleton Tests
- Alias-Unterstuetzung: `/api/v1/modules` <-> `/api/v1/moduls`

### Test Coverage 61% (Kern-Module: 75-93%)

**Coverage nach Modul**
| Modul | Coverage |
|-------|----------|
| cache | 93% |
| monitoring | 87% |
| security | 75% |
| **Gesamt (Kern-Module)** | **61%** |

**Test-Infrastruktur**
- 177 Test-Dateien
- 186 Python-Test-Module
- pytest-aiohttp Fixtures fuer async Tests
- .coveragerc mit korrekter Source-Konfiguration

### HA Integration 13.0.4

**Manifest-Sync**
- `manifest.json` synchronisiert mit `config.json` (v13.0.4)
- `config.yaml` auf v13.0.4 aktualisiert
- `VERSION` File auf v13.0.4
- `build.yaml` konform mit HA Add-on Standard

**Backend Health Check**
- `/api/styx/health/backend` -- Backend-Services Health Status
- Core Add-on Validierung
- Health- und Metrics-Tests

### 3D Vision Features

**vision3d.js**
- Neue JavaScript-Komponente fuer 3D-Visualisierung
- Integration mit bestehendem Dashboard
- Coverage-Konfiguration in pytest

---

## Security

- Backend-Services Health Check mit Auth-Validation
- Admin-Token Enforced fuer sensitive Operations
- Rate Limiting fuer RAG API

---

## Weitere Aenderungen

- **Connection Pooling**: Wiederverwendbare aiohttp.ClientSession (100% Reuse-Rate)
- **RAG Search API**: Hybrid Search mit SearXNG Integration
- **Startup Profiling**: Bottleneck-Identifikation beim Start
- **TTL-based Caching**: RAG Search Results mit konfigurierbarer TTL

---

## Upgrade-Hinweise

### Kompatibilitaet
- **Breaking Changes:** Keine
- **Neue Dependencies:** aiohttp (bereits in requirements.txt)
- **Konfiguration:** Bestehende Configs bleiben kompatibel

### Migration
```bash
# Standard-Upgrade (Docker Pull)
ha addons update pilotsuite_core

# Manuell (fuer Entwickler)
git pull origin main
docker build -t pilotsuite-core .
```

---

## Naechste Phase: Phase 7 (Production Readiness)

- Advanced ML (On-Device Inference, Anomaly Detection)
- OpenAPI-Spec-Erweiterung
- Performance Monitoring & Optimization

---

**PilotSuite v13.0.4** -- Local-first, Privacy-first, Governance-first.
