# OFFENE_FRAGEN_STXY — Entscheidungen PilotClaw (2026-03-20)

> Andreas: "Eigenständig und autonom die beste Lösung finden."
> Diese Entscheidungen gelten bis Stxy sie override.

## D-01: zone_type Semantic Clash ✅ ENTSCHIEDEN

**Entscheidung:** Orthogonal-Dimension-Muster.

**Begründung:** `zone_type` in Core (funktional: living/kitchen/bath) und HA (physisch: room/area/outdoor) sind zwei verschiedene Dimensionen. Ein Enum-Feld kann nicht beides.

**Lösung:**
- Core behält `zone_type` als funktionale Klassifizierung
- HA führt separates Feld `habitus_zone_type` ein (für die physische Hierarchie)
- In der Core→HA Sync-Schnittstelle wird explizit gemappt
- UI zeigt Core-zone_type für Menschen, intern wird HA-zone_type verwendet

## D-02: zone_id Namespace Drift ✅ ENTSCHIEDEN

**Entscheidung:** Explizite `ha_zone_id`-Mapping einführen.

**Lösung:**
- Core API bekommt optionales Feld `ha_zone_id` in `ZoneResponse`
- HA speichert `zone_id` als `zone:wohnbereich` intern
- Core mappt `zone_type: "living"` → `ha_zone_id: "zone:wohnbereich"` über Mapping-Table
- Sync-Endpunkt `POST /zones/sync` nimmt `{ha_zone_id, core_zone_type}` entgegen

## D-03: Zone-Aggregationen ✅ ENTSIEDEN

**Entscheidung:** N:1-Aggregationen BEIBEHALTEN, aber als expliziter dokumentierter Contract.

**Lösung:**
- Aggregationen werden in `ZONE_AGGREGATION_MAP` dokumentiert (nicht implizit)
- `esszimmer → wohnbereich`, `dining → wohnbereich`
- `gang → gangbereich`
- `terrasse/balkon/loggia → aussenbereich`
- `garten/hof/garage → aussenbereich`
- Jede Aggregation hat expliziten Confidence-Wert
- Ungeordnet bleibt Fallback für alles andere

---

## Files: 16 geparkt → branch `pilot/parked-2026-03-20`

Alle 16 Files werden auf `pilot/parked-2026-03-20` gepusht. Stxy kann reviewen und entscheiden was merged wird.

## Nächste Schritte PilotClaw (HA-Spur)

1. `habitus_zone_type`-Feld in HA-Zone-Modellen einführen
2. `ZONE_AGGREGATION_MAP` dokumentieren
3. PS-171 ConfigEntry Delta-Write umsetzen
4. PS-170 Reconfigure-Step implementieren
