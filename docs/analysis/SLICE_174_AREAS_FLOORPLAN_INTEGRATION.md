# Slice 174: Areas/Floorplan Integration

**Status:** Analyzed (2026-04-05)
**Basis:** areas.py + floorplan.py (Slice 166/167)

## Problemstellung
Areas und Floorplans existieren als separate Silos. Ein echtes Read-Model benötigt die Verknüpfung:
- Welcher Floorplan gehört zu welchem Area-Level?
- Welche Zone auf dem Floorplan repräsentiert welches Area/Sub-Area?

## Target API Expansion

1. **Area ↔ Floorplan Mapping**
   - GET /api/v1/areas/<id>/floorplan
   - PUT /api/v1/areas/<id>/floorplan
2. **Floorplan Zone Resolve**
   - GET /api/v1/floorplan/<id>/zones/resolve (Mapper zu Areas)
3. **Cross-Service Navigation**
   - Navigation von Area-Tree direkt in Floorplan-Koorindaten

## Decision
Erweiterung beider Blueprints um Cross-References.

