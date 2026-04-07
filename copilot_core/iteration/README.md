# Continuous Improvement Engine

**Harte Iterationsschleife** für automatisierte Systemverbesserungen.

## Überblick

Diese Engine implementiert einen kontinuierlichen Verbesserungsprozess:

1. **Metriken sammeln** — Performance, Errors, User-Feedback (simuliert)
2. **Auto-Identifikation** — Erkennt Verbesserungspotenziale automatisch
3. **Low-Risk-Implementation** — Implementiert sichere Optimierungen automatisch
4. **High-Risk-Reporting** — Erstellt Reports für manuelle Prüfung
5. **Git-Commit** — Commitet Änderungen auf `takeover/main`

## Architektur

```
copilot_core/iteration/
├── __init__.py              # Package-Exports
├── iteration_loop.py        # Haupt-Engine
├── test_iteration_loop.py   # Unit-Tests (17 Tests)
├── cache.py                 # Auto-generated Caching-Modul
├── state.json               # Iterations-Status (auto-generated)
└── README.md                # Diese Datei
```

## Komponenten

### `MetricsCollector`
Sammelt Metriken aus:
- Performance-Daten (Response-Time, Throughput, Memory)
- Error-Logs (Error-Rate, Critical Errors)
- User-Feedback (Satisfaction, Feature Requests, Bugs)

### `ImprovementIdentifier`
Identifiziert Verbesserungen durch:
- Metrik-Analyse (Threshold-basiert)
- Code-Scan (TODO/FIXME Kommentare)
- Pattern-Erkennung (Duplikate, ungenutzte Imports)

### `LowRiskImplementer`
Implementiert automatisch:
- Caching-Optimierungen
- TODO/FIXME-Auflösung
- Generische Code-Verbesserungen

### `HighRiskReporter`
Erstellt Markdown-Reports für:
- Critical-Risk Änderungen
- High-Risk Änderungen
- Medium-Risk Änderungen (zur Information)

### `GitManager`
Verwaltet Git-Operationen:
- Checkout von `takeover/main`
- Add & Commit
- Push zu Origin

## Verwendung

### Einmalige Iteration

```bash
cd /config/clawd
python3 -m copilot_core.iteration.iteration_loop
```

### Kontinuierlicher Modus

```bash
python3 -m copilot_core.iteration.iteration_loop --continuous --interval 60
```

### CLI-Optionen

| Option | Beschreibung | Default |
|--------|--------------|---------|
| `--workspace` | Workspace Root | `/config/clawd` |
| `--branch` | Git Branch | `takeover/main` |
| `--continuous` | Kontinuierlicher Modus | `false` |
| `--interval` | Intervall in Minuten | `60` |
| `--verbose` | Debug-Logging | `false` |

### Python API

```python
from copilot_core.iteration import ContinuousImprovementEngine
from pathlib import Path

engine = ContinuousImprovementEngine(Path("/config/clawd"))
report = engine.run_iteration()

print(f"Iteration: {report.iteration_id}")
print(f"Status: {report.status}")
print(f"Metriken: {report.metrics_collected}")
print(f"Verbesserungen: {report.improvements_identified}")
print(f"Implementiert: {report.improvements_implemented}")
```

## Risikoklassifikation

| Level | Beschreibung | Aktion |
|-------|--------------|--------|
| **LOW** | Sichere Optimierungen | Auto-Implement |
| **MEDIUM** | Moderate Änderungen | Report + Review |
| **HIGH** | Signifikante Änderungen | Report + Manual Approval |
| **CRITICAL** | Kritische Änderungen | Report + Lead Review |

## Metriken

### Performance
- `response_time_avg` — Durchschnittliche Response-Time (ms)
- `throughput` — Anfragen pro Minute
- `memory_usage` — Speichernutzung (%)

### Errors
- `error_rate` — Fehlerrate (%)
- `critical_errors` — Kritische Fehler (24h)
- `runtime_errors` — Laufzeitfehler aus Logs

### User-Feedback
- `user_satisfaction` — Zufriedenheit (1-5)
- `feature_requests` — Offene Requests
- `bug_reports` — Gemeldete Bugs

## Tests

```bash
cd /config/clawd
python3 -m pytest copilot_core/iteration/test_iteration_loop.py -v
```

**Ergebnis:** 17 Tests ✅

## State-Management

Der Iterations-Status wird in `state.json` gespeichert:

```json
{
  "last_iteration": {
    "iteration_id": "iter_20260406_221500",
    "status": "completed",
    "metrics_collected": 8,
    "improvements_identified": 3,
    "improvements_implemented": 2
  },
  "improvements": [...],
  "timestamp": "2026-04-06T22:15:30"
}
```

## Reports

High-Risk-Reports werden gespeichert unter:
```
/reports/iteration/high_risk_report_YYYYMMDD_HHMMSS.md
```

## Integration

### Home Assistant Integration (geplant)

```yaml
# configuration.yaml
automation:
  - alias: "Continuous Improvement Loop"
    trigger:
      platform: time_pattern
      minutes: "/60"
    action:
      service: python_script.iteration_loop
```

### Cron-Job

```bash
# Alle 60 Minuten
0 * * * * cd /config/clawd && python3 -m copilot_core.iteration.iteration_loop >> /var/log/iteration.log 2>&1
```

## Sicherheit

- **Keine externen API-Calls** — Alle Operationen sind lokal
- **Git-Safety** — Nur auf `takeover/main` Branch
- **Rollback-fähig** — Jeder Commit ist revertierbar
- **Logging** — Alle Aktionen werden protokolliert

## Nächste Schritte

1. ✅ Core-Engine implementiert
2. ✅ Unit-Tests (17/17 bestanden)
3. ✅ Dokumentation erstellt
4. ⏳ Integration in Home Assistant
5. ⏳ Echte Metriken aus HA-Logs
6. ⏳ ML-basierte Verbesserungserkennung

## Lizenz

Teil der PilotSuite — Internal Use Only
