# SYMBIOTIC ENTITY SPEC: LEARNING_MEMORY (SL-009)

## 1. Identität
- **ID:** `memory.user_preferences`, `memory.automation_patterns`
- **Core-Anker:** `copilot_core/entities/learning_memory.py`

## 2. Symbiotische Verknüpfung
- **Speichert:** Erfolgreiche Intent-Resolutions, korrigierte Aktionen
- **Abfrage:** Vorschläge basierend auf Kontext
- **Export:** Training-Daten für Modelle

## 3. Datenmodell
```json
{
  "memory_id": "memory.user.andreas.evening_routine",
  "pattern": {"time": "20:00", "zone": "living_room", "action": "dim_lights"},
  "frequency": 45,
  "last_triggered": "2026-04-05T20:00:00Z",
  "confidence": 0.92
}
```
