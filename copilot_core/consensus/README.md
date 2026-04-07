# Konsens-Engine für Agenten-Entscheidungen

Entscheidungs-Framework für strittige Fragen im PilotSuite-Agenten-Team.

## Features

- **Voting-Mechanismen**: Majority, Super-Majority, Unanimous, Weighted
- **Decision-Logging**: Vollständiger Audit-Trail für alle Entscheidungen
- **Auto-Resolution**: Automatische Auflösung bei Low-Priority-Entscheidungen
- **Git-Integration**: Optionaler Commit von Decision-Logs ins Repository

## Installation

```python
from copilot_core.consensus import (
    ConsensusEngine,
    VoteType,
    VoteWeight,
    VotingMethod,
    DecisionStatus,
)
```

## Quick Start

```python
from pathlib import Path
from copilot_core.consensus import ConsensusEngine, VoteType, VotingMethod

# Engine initialisieren
engine = ConsensusEngine(log_dir=Path("./decision_logs"))

# Entscheidung erstellen
decision = engine.create_decision(
    title="Neue Feature-Priorität",
    description="Welches Feature zuerst implementieren?",
    priority="medium",
    voting_method=VotingMethod.MAJORITY,
)

# Stimmen abgeben
engine.submit_vote(decision.id, "homeclaw", VoteType.YES, rationale="Wichtig für User")
engine.submit_vote(decision.id, "orakel", VoteType.YES)
engine.submit_vote(decision.id, "designclaw", VoteType.NO)

# Ergebnis prüfen
print(f"Status: {decision.status.value}")
print(f"Ergebnis: {decision.result}")
```

## Voting-Methoden

### Majority (Einfache Mehrheit)
- >50% der Stimmen müssen YES sein
- Mindestens 2 Stimmen erforderlich

```python
decision = engine.create_decision(
    title="Standard-Entscheidung",
    voting_method=VotingMethod.MAJORITY,
)
```

### Super-Majority (2/3 Mehrheit)
- ≥66.7% der Stimmen müssen YES sein
- Für wichtigere Entscheidungen

```python
decision = engine.create_decision(
    title="Wichtige Änderung",
    voting_method=VotingMethod.SUPER_MAJORITY,
)
```

### Unanimous (Einstimmig)
- Alle Teilnehmer müssen YES oder ABSTAIN wählen
- VETO möglich (sofortige Ablehnung)
- Für kritische Changes

```python
decision = engine.create_decision(
    title="Breaking Change",
    voting_method=VotingMethod.UNANIMOUS,
    required_participants=["homeclaw", "pilotclaw", "orakel"],
)

# Veto mit Begründung
engine.submit_vote(decision.id, "orakel", VoteType.VETO, rationale="Sicherheitsrisiko")
```

### Weighted (Gewichtete Stimmen)
- Stimmen haben unterschiedliches Gewicht je nach Rolle
- Net-Wert > 0 = Approved, < 0 = Rejected

```python
from copilot_core.consensus import VoteWeight

engine.submit_vote(decision.id, "team_member", VoteType.YES, VoteWeight.STANDARD)  # 1
engine.submit_vote(decision.id, "expert", VoteType.YES, VoteWeight.EXPERT)         # 2
engine.submit_vote(decision.id, "lead", VoteType.YES, VoteWeight.LEAD)             # 3
engine.submit_vote(decision.id, "andreas_betz", VoteType.YES, VoteWeight.OWNER)    # 5
```

## Stimmgewichte

| Gewicht | Wert | Rolle |
|---------|------|-------|
| STANDARD | 1 | Team-Mitglieder |
| EXPERT | 2 | Fachexperten |
| LEAD | 3 | Tech-Leads |
| OWNER | 5 | Andreas Betz (letztes Wort) |

## Prioritäten

| Priorität | Auto-Resolution | Beschreibung |
|-----------|-----------------|--------------|
| low | Ja (nach Timeout) | Kosmetik, Dokumentation |
| medium | Nein | Standard-Features |
| high | Nein | Wichtige Änderungen |
| critical | Nein | Breaking Changes, Security |

## Auto-Resolution

Low-Priority-Entscheidungen werden automatisch aufgelöst wenn keine Abstimmung erfolgt:

```python
decision = engine.create_decision(
    title="Dokumentation-Farbgebung",
    priority="low",
    auto_resolve_after_hours=24,  # Nach 24 Stunden auto-auflösen
)

# Regelmäßig prüfen (z.B. via Cron)
auto_resolved = engine.check_auto_resolution()
```

## Audit-Trail

Alle Entscheidungen werden geloggt:

```python
# Decision-Log exportieren
export_path = engine.export_decision_log(decision.id)
# → ./decision_logs/decision_DEC-20260406201814-abc123.json

# Historie abrufen
history = engine.get_decision_history(limit=100)
for log in history:
    print(f"{log.timestamp}: {log.action} by {log.agent_id}")
```

## Git-Commit Integration

Automatische Commits von Decision-Logs:

```python
engine = ConsensusEngine(
    log_dir=Path("./decision_logs"),
    auto_commit=True,
    git_repo=Path("/config/clawd"),
)
```

## Callbacks

Events für Veto und Resolution:

```python
def on_veto(decision):
    print(f"Veto: {decision.result}")

def on_resolve(decision):
    print(f"Resolved: {decision.result}")

engine.on_veto(on_veto)
engine.on_resolve(on_resolve)
```

## Beispiel-Anwendungen

Siehe `example_usage.py` für vollständige Beispiele:
- Majority-Entscheidungen
- Unanimous mit Veto
- Weighted Voting mit Owner
- Auto-Resolution
- Audit-Trail Export

## Decision-ID Format

```
DEC-{YYYYMMDDHHMMSS}-{title_hash}
```

Beispiel: `DEC-20260406201814-5e6e31c4`

## Tests

```bash
cd /config/clawd
python3 -m pytest copilot_core/consensus/test_consensus_engine.py -v
```

## Architektur

```
copilot_core/consensus/
├── __init__.py              # Public API
├── consensus_engine.py      # Haupt-Engine
├── test_consensus_engine.py # Test-Suite
├── example_usage.py         # Anwendungsbeispiele
└── README.md                # Diese Datei
```

## Integration mit Agenten

```python
# In Agenten-Code
from copilot_core.consensus import ConsensusEngine, VoteType, VotingMethod

class AgentWithConsensus:
    def __init__(self):
        self.consensus = ConsensusEngine()
    
    def propose_change(self, change_description):
        decision = self.consensus.create_decision(
            title=f"Change: {change_description[:50]}",
            description=change_description,
            priority="medium",
            voting_method=VotingMethod.MAJORITY,
        )
        return decision.id
    
    def vote_on_proposal(self, decision_id, vote_type, rationale=None):
        return self.consensus.submit_vote(
            decision_id=decision_id,
            agent_id=self.agent_id,
            vote_type=vote_type,
            rationale=rationale,
        )
```

## Best Practices

1. **Richtige Voting-Methode wählen**:
   - Standard → Majority
   - Breaking Changes → Unanimous
   - Budget/Resource → Weighted

2. **Required Participants setzen** bei wichtigen Entscheidungen

3. **Rationale angeben** für Nachvollziehbarkeit

4. **Priority korrekt wählen** um Auto-Resolution zu vermeiden

5. **Regelmäßig exportieren** für Compliance

## License

Teil von PilotSuite / OpenClaw
