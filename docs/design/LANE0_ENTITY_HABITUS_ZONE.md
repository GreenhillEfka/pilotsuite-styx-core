# SYMBIOTIC ENTITY SPEC: HABITUS_ZONE (SL-001)

## 1. Identität
- **ID:** `zone.hallway`, `zone.living_room`
- **Core-Anker:** `copilot_core/entities/zone.py`

## 2. Symbiotische Verknüpfung
- **HA-Schatten:** Spiegelt HA Area-ID.
- **Context-Bridge:** Hält BM25-Indizes für raumspezifische Befehle.
- **Neuron-Link:** Jede Zone hat ein lokales "Gedächtnis" (letzte 50 Ereignisse).

## 3. Datenmodell (Draft)
```json
{
  "zone_id": "string",
  "metadata": {"name": "string", "type": "room|area|outdoor"},
  "symbiosis": {
    "linked_entities": ["light.living", "media_player.sonos"],
    "habitus_rules": ["rule_123"],
    "active_context": "ready"
  }
}
```
