# SDK Schema Gate - PS-134

## Entscheidung: `x-separate_input_output_schemas: false`

### Analyse

Geprüfte Dateien im `release-prep/v14.7.3` Worktree:
- `docs/openapi.yaml`
- `copilot_core/docs/openapi.yaml`

**Befund:** Beide Specs haben bereits manuell getrennte Input/Output-Schemas:
- `Candidate` (Output mit id, created_at, etc.)
- `CandidateInput` (Input ohne id, created_at, etc.)

### Begründung

- **Stabilität:** Mit `false` verwendet das SDK die explizit definierten Schemas direkt
- **Keine Duplikation:** Vermeidet doppelte Modell-Generierung
- **Bestehend:** Das Muster ist bereits implementiert und funktioniert

### Änderungen

| Datei | Änderung |
|-------|----------|
| `docs/openapi.yaml` | `x-separate_input_output_schemas: false` hinzugefügt |
| `copilot_core/docs/openapi.yaml` | `x-separate_input_output_schemas: false` hinzugefügt |

### Verifikation

```bash
# Syntax-Prüfung via Python yaml
python3 -c "import yaml; yaml.safe_load(open('docs/openapi.yaml'))"
python3 -c "import yaml; yaml.safe_load(open('copilot_core/docs/openapi.yaml'))"
```

### Commit

```
feat(openapi): add x-separate_input_output_schemas: false for SDK stability

- Both specs already have manual Input/Output schema separation
- Using false ensures SDK uses explicit schemas directly
- Prevents duplicate model generation
```