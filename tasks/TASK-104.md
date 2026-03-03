# TASK-104: Core Add-on Config validieren (HA Conformance)

**Status:** ✅ COMPLETED  
**Datum:** 2026-03-03 18:34 GMT+1  
**Role:** Builder

## Ergebnis

### HA Add-on Conformance Check Durchgeführt

**Geprüfte Konfiguration:**
- `copilot_core/config.yaml`
- `copilot_core/manifest.json`

### Gefundenes Problem

**Options/Schema Mismatch in manifest.json:**
- `searxng_enabled` und `searxng_base_url` waren im `schema` definiert
- Aber fehlten in den `options`
- `config.yaml` hatte beide bereits korrekt

### Lösung

**manifest.json repariert:**
```json
"options": {
  ...
  "conversation_enabled": true,
  "searxng_enabled": true,           // HINZUGEFÜGT
  "searxng_base_url": "http://192.168.30.18:4041"  // HINZUGEFÜGT
}
```

### Conformance Testsuite Erstellt

**File:** `tests/test_addon_config.py`

**18 Tests in 2 Klassen:**

#### TestHAAddonConfig (15 Tests)
- ✅ `test_manifest_exists` - manifest.json vorhanden
- ✅ `test_config_exists` - config.yaml vorhanden
- ✅ `test_manifest_valid_json` - Valid JSON
- ✅ `test_required_fields` - Alle HA-required fields
- ✅ `test_version_format` - Semver (X.Y.Z)
- ✅ `test_architecture_valid` - amd64/aarch64
- ✅ `test_startup_value` - services (valid)
- ✅ `test_slug_format` - copilot_core (valid)
- ✅ `test_ingress_consistency` - Ingress + Port konsistent
- ✅ `test_options_schema_match` - Options/Schema sync
- ✅ `test_schema_types_valid` - Schema types valid
- ✅ `test_version_sync` - Sync mit VERSION file
- ✅ `test_config_yaml_sync` - config.yaml/manifest.json sync
- ✅ `test_ports_format` - Port definition format
- ✅ `test_map_format` - Volume mounts format

#### TestConfigOptions (3 Tests)
- ✅ `test_auth_token_optional` - auth_token ist optional (?)
- ✅ `test_log_level_options` - log_level list type
- ✅ `test_conversation_options_present` - Conversation options vorhanden

### Test Resultat
```bash
pytest -q tests/test_addon_config.py
18 passed in 0.49s
```

## Commit Hash
`9ce3c2b` — fix: HA Add-on config conformance - sync searxng options in manifest.json

## Artifact Paths (Files Changed)
- `copilot_core/manifest.json` (searxng options added)
- `copilot_core/rootfs/usr/src/app/tests/test_addon_config.py` (new test suite)
- `tasks/TASK-104.md` (Task-Report)

## HA Conformance Summary

| Check | Status |
|-------|--------|
| Required Fields | ✅ |
| Version Format (13.0.4) | ✅ |
| Architecture (amd64, aarch64) | ✅ |
| Startup (services) | ✅ |
| Ingress Consistency | ✅ |
| Options/Schema Sync (12 fields) | ✅ |
| Config.yaml/Manifest Sync | ✅ |

## Known Issues
Keine - alle Conformance-Tests grün.

## Next Steps
- Task als abgeschlossen markieren
- Config ist HA Add-on konform
