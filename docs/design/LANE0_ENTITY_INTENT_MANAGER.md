# SYMBIOTIC ENTITY SPEC: INTENT_MANAGER (SL-004)

## 1. Identität
- **ID:** `intent.lights_on_evening`, `intent.media_chill_mode`
- **Core-Anker:** `copilot_core/entities/intent_manager.py`

## 2. Symbiotische Verknüpfung
- **Input:** Sprache, Zeit, Kontext, Präsenz
- **Resolution:** Mapped zu Actions (Device Link + Room Context)
- **Learning:** Speichert erfolgreiche Resolutions für Vorschläge

## 3. Datenmodell
```json
{
  "intent_id": "string",
  "trigger_phrases": ["dim the lights", "cozy mode"],
  "context_required": ["zone", "time"],
  "actions": [{"device": "light.living", "command": "dim", "value": 50}],
  "confidence_threshold": 0.8
}
```
