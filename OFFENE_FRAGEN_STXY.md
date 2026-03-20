# Offene Fragen — Sync dirty Files (PilotClaw → Stxy)
**Datum:** 2026-03-20
**Referent:** PilotClaw (Subagent)

---

## 1. Fragmentarische Files — Parken oder einbauen?

Die folgenden **neuen** Files sind unstaged (不存在 in git). Sind sie als Bausteine für eine laufende Arbeit gedacht, oder sollen sie verworfen werden?

| File | Status | Vermutung |
|------|--------|-----------|
| `copilot_core/api/v1/proposals.py` | ✅ New | Proposal-Engine-Skeleton, fehlt Integration in habitus.py |
| `copilot_core/api/v1/zone_config.py` | ✅ New | Zone-Config-CRUD-Skeleton |
| `copilot_core/api/v1/module_config.py` | ✅ New | Modul-Config-Skeleton |
| `copilot_core/api/v1/openapi_spec.yaml` | ✅ New | Alternative OpenAPI-Variante? |
| `copilot_core/api/v1/tags.py` | ✅ New | Tags-Skeleton |
| `copilot_core/api/v1/README.md` | ✅ New | API-Doku in Arbeit |
| `copilot_core/rootfs/usr/src/app/copilot_core/habitat/` | ✅ New | `__init__.py` + `contracts.py` |
| `copilot_core/rootfs/usr/src/app/copilot_core/tests/test_zone_proposals.py` | ✅ New | Unklar ob für proposals.py |
| `copilot_core/rootfs/usr/src/app/tests/test_habitat_contracts.py` | ✅ New | Test für habitat/contracts.py |
| `copilot_core/rootfs/usr/src/app/tests/test_zone_proposal_action_pipeline.py` | ✅ New | Test für Action-Pipeline |
| `docs/architecture/` | ✅ New | Architektur-Doku? |
| `docs/integrations/ha_habitus_zone_mapping.md` | ✅ New | HA-Mapping-Doku? |
| `requirements-dev.txt` | ✅ New | Dev-Dependencies? |
| `tests/test_zone_config_api.py` | ✅ New | Test für zone_config.py |
| `.github/workflows/release-gate.yml` | ✅ New | Release-Gate-Workflow |
| `RELEASE_NOTES_TEMPLATE.md` | ✅ New | Release-Notes-Template? |
| `RELEASE_POLICY.md` | ✅ New | Release-Policy-Doku? |

**Frage an Stxy:** Sollen diese Files committed werden (mit eigener Changelog-Gruppe), oder sind sie Work-in-Progress und sollen bis zur Fertigstellung geparkt bleiben?

---

## 2. ZoneType-Konsistenz: TERRACE → OUTSIDE

Alle Outdoor-Aliase (Terrasse, Balkon, Loggia, Terrassentuer) werden jetzt auf `ZoneType.OUTSIDE` kanonisiert — **nicht** mehr auf `TERRACE`.

- `zone_matcher.py`: `_match_outdoor_canonical_alias()` pushing → OUTSIDE
- `test_zone_matching.py`: `test_terrace_match` updated, `test_outdoor_aliases_match_outside` neu
- `habitus_zones.py`: OUTSIDE-Prio angepasst?

**Frage:** Soll `TERRACE` als separater ZoneType erhalten bleiben? Falls ja, muss `zone_matcher.py` angepasst werden (Küchenbereich→KITCHEN, Terrasse→TERRACE).

---

## 3. docs/openapi.yaml — Wo ist die Source of Truth?

Drei OpenAPI-Dateien:
1. `copilot_core/docs/openapi.yaml` (FastAPI)
2. `copilot_core/rootfs/usr/src/app/docs/openapi.yaml` (Flask)
3. `docs/openapi.yaml` (Extra, +119 Zeilen mit `/api/v1/zones/assign`)

`docs/openapi.yaml` enthält die `/zones/assign`-Endpoint-Definition als PS-133-Pilot, aber die anderen beiden wurden nur minimal synchronisiert.

**Frage:** Ist `docs/openapi.yaml` die Architektur-OpenAPI (Hauptdokumentation) oder eine separate? Wer pflegt welche?

---

## 4. habitus_zones.py — 469 Zeilen Diff (doppelte Files)

`copilot_core/homeassistant/habitus_zones.py` UND `copilot_core/rootfs/usr/src/app/copilot_core/homeassistant/habitus_zones.py` haben jeweils ~469 Zeilen Diff. Beide scheinen denselben Inhalt zu haben (module_overrides, DEFAULT_SUGGESTION_MODE etc.).

**Frage:** Ist diese Duplizierung beabsichtigt (separate FastAPI vs. Flask-Versionen)? Oder sollte eine Version die andere als Basis nehmen?

---

## 5. CHANGELOG.md — Nicht committed

`CHANGELOG.md` hat unstaged Changes. Soll ich eine Changelog-Gruppe committen oder machst du das selbst?

---

## 6. Commit-Historie (11 Commits)

```
95f40441 feat(api): add shared ErrorResponse model
95bbd3dd feat(zones): canonical outdoor aliases
c26446e3 feat(zones): ZoneResponse extended, ErrorResponse wired
0d64baa3 feat(zones): module_overrides per zone type
63cb877b feat(habitus-zones-api): module_overrides in GET/POST configure
54c088af feat(presence): v3.4.0 multi-source aggregation
6f3d0bde feat(miner): _bucket_numeric_sensor_state() semantic bucketing
fa023b4a feat(zone-mining): ZoneBasedMiner class + proposal pipeline
a6cc4bec feat(habitus-api): /zone-proposals GET+POST + accept
f6cb54d6 test(zones): module_overrides, outdoor aliases, kuechenbereich canonical
f5d00242 feat(zone-editor): updated API endpoints v1
ef4f1642 docs(openapi): sync OpenAPI specs, /zones/assign pilot, v14.7.3
```

Alle Python-Files: `py_compile` ✅ — keine Syntax-Fehler.
