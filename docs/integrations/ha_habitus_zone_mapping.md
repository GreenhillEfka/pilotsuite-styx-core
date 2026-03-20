# Home Assistant → Habituszonen Mapping

## Kurznotiz

Die Zone-Matching-Logik aggregiert jetzt Home-Assistant-`areas` und `entities` direkt in PilotSuite-Habituszonen.

- **Bereiche zuerst:** Sichere Area-Matches (`Wohnzimmer`, `Gäste-WC`, `Büro`, `Terrasse` usw.) werden zur primären Quelle für die Zonenzuordnung.
- **Entitäten erben Areas:** Hat eine Entität ein sicheres `area_id`, landet sie automatisch in derselben Habituszone.
- **Entity-Fallback:** Wenn keine sichere Area existiert, wird über `friendly_name`, `name` und `entity_id` erneut gematcht.
- **Unsicher = `ungeordnet`:** Niedrige Confidence oder nicht eindeutig lesbare Namen werden nicht mehr blind in eine Zone geschoben, sondern im Sammelbereich `ungeordnet` abgelegt.
- **Smart aggregiert:** Mehrere HA-Bereiche können in dieselbe Habituszone zusammenlaufen; die API liefert dafür pro Zone aggregierte `area_ids`, `area_names` und `entities`.

## API-Hinweis

Neu im Flask-Habitus-API:

- `POST /api/v1/habitus/zones/map-homeassistant`

Neu im FastAPI-Zonenrouter:

- `POST /api/v1/zones/map/homeassistant`

Beide Endpunkte erwarten:

```json
{
  "areas": [{"area_id": "wohnzimmer", "name": "Wohnzimmer"}],
  "entities": [
    {
      "entity_id": "light.wohnzimmer_decke",
      "attributes": {
        "friendly_name": "Wohnzimmer Decke",
        "area_id": "wohnzimmer"
      }
    }
  ]
}
```

## Geänderte Dateien

- `copilot_core/homeassistant/zone_matcher.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/homeassistant/zone_matcher.py`
- `copilot_core/api/v1/zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/tests/test_zone_matching.py`
- `copilot_core/rootfs/usr/src/app/tests/test_habitus_zones_api.py`
- `pilotsuite-styx-ha/custom_components/copilot_ha/entity_discovery.py` (separate HA working tree)
