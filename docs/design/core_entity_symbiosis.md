# Core Entity Symbiosis: Zonen-Matrize & Rollen-Standard

**Status:** Draft / Content Evolution
**Zieldokument:** `docs/design/core_entity_symbiosis.md`
**Kontext:** PilotSuite Styx Core / Habitus-Zonen

## 1. Zonen-Typen (Archetypen)
Standardisierte Zonen-Typen für die PilotSuite zur Gewährleistung konsistenter Automationslogik.

| Zone-Type | Beschreibung | Standard-Module |
| :--- | :--- | :--- |
| `living` | Wohn- und Essbereiche | Light, Motion, Music, Volume, TV, Climate |
| `bath` | Sanitärbereiche | Light, Motion, Climate |
| `kitchen` | Kochbereiche | Light, Motion, Music, Volume, Climate |
| `office` | Arbeitsbereiche | Light, Motion, Music, Volume, Climate |
| `hallway` | Durchgangsbereiche | Light, Motion, Camera |
| `bedroom` | Schlafbereiche | Light, Motion, Music, Volume, Climate |
| `outside` | Außenbereiche allgemein | Light, Motion, Camera |
| `terrace` | Terrassen/Balkone | Light, Motion, Music, Volume, Camera |

## 2. Intelligente Core-Entitäten (Entity-Roles)
Weg von der "dummen" HA-Entität hin zur Rolle im Core-Gefüge.

### Standard-Rollen pro Zone
Jede Zone erwartet eine Auswahl dieser Rollen für die volle Funktionstiefe:

| Rolle | Core-Key | Erwartet in | Beschreibung |
| :--- | :--- | :--- | :--- |
| **Primary Light** | `primary_light` | Alle | Hauptlichtquelle, wird bei Anwesenheit primär gesteuert. |
| **Ambient Light** | `ambient_light` | living, bedroom | Akzentbeleuchtung für Moods. |
| **Motion Master** | `motion_master` | Alle | Primärer Präsenzmelder (PIR/mmWave Fusion). |
| **Ambient Sound** | `ambient_sound` | living, kitchen, bath | Primärer Media-Player für Musikwolke. |
| **Temperature Master**| `temp_master` | Alle | Referenzsensor für Klimasteuerung. |
| **Window/Door** | `opening_sensor`| Alle | Kontakt-Sensoren für Sicherheits- & Heizungslogik. |

## 3. Implementierungs-Pfad (Handoff PilotClaw)
1. **Discovery:** HA-Entitäten werden über `/api/v1/zone-automation/sync-definitions` gemappt.
2. **Role Mapping:** PilotClaw weist Rollen (`primary_light` etc.) basierend auf Metadaten oder User-Input zu.
3. **Core Sync:** Core nutzt die Rollen in `ZoneAutomationController` zur Steuerung.

## 4. Semantische Tiefe
Zonen sind nicht nur Gruppen, sondern Verhaltenscontainer. Ein `ZoneType.BEDROOM` triggert im Core eine restriktivere Suggestion-Logik für Medien als ein `ZoneType.LIVING`.
