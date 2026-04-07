"""
Beispiel: Verwendung der Konsens-Engine

Demonstriert typische Anwendungsfälle für Agenten-Entscheidungen.
"""

from pathlib import Path
from consensus_engine import (
    ConsensusEngine,
    VoteType,
    VoteWeight,
    VotingMethod,
)


def example_majority_decision():
    """Beispiel: Einfache Mehrheitsentscheidung."""
    engine = ConsensusEngine(log_dir=Path("./decision_logs"))

    decision = engine.create_decision(
        title="Neue Feature-Priorität",
        description="Soll die Musikwolke oder der Sonnenwecker zuerst implementiert werden?",
        priority="medium",
        voting_method=VotingMethod.MAJORITY,
    )

    # Agenten stimmen ab
    engine.submit_vote(decision.id, "homeclaw", VoteType.YES, rationale="Musikwolke ist wichtiger")
    engine.submit_vote(decision.id, "designclaw", VoteType.NO, rationale="Sonnenwecker hat höhere Priorität")
    engine.submit_vote(decision.id, "orakel", VoteType.YES, rationale="Stimme Musikwolke zu")

    print(f"Entscheidung: {decision.title}")
    print(f"Status: {decision.status.value}")
    print(f"Ergebnis: {decision.result}")
    print()


def example_unanimous_critical():
    """Beispiel: Einstimmige Entscheidung für kritisches Change."""
    engine = ConsensusEngine(log_dir=Path("./decision_logs"))

    decision = engine.create_decision(
        title="API-Breaking-Change",
        description="Soll die /core/v2 API die alte /core/v1 vollständig ersetzen?",
        priority="critical",
        voting_method=VotingMethod.UNANIMOUS,
        required_participants=["homeclaw", "pilotclaw", "orakel"],
    )

    # Alle müssen zustimmen
    engine.submit_vote(decision.id, "homeclaw", VoteType.YES, VoteWeight.LEAD)
    engine.submit_vote(decision.id, "pilotclaw", VoteType.YES, VoteWeight.EXPERT)
    engine.submit_vote(decision.id, "orakel", VoteType.YES, VoteWeight.LEAD)

    print(f"Entscheidung: {decision.title}")
    print(f"Status: {decision.status.value}")
    print(f"Ergebnis: {decision.result}")
    print()


def example_weighted_owner_decision():
    """Beispiel: Gewichtete Entscheidung mit Owner-Veto."""
    engine = ConsensusEngine(log_dir=Path("./decision_logs"))

    decision = engine.create_decision(
        title="Budget-Freigabe für Cloud-Upgrade",
        description="Soll das monatliche Budget für Cloud-Services erhöht werden?",
        priority="high",
        voting_method=VotingMethod.WEIGHTED,
    )

    # Team stimmt zu, Owner hat letztes Wort
    engine.submit_vote(decision.id, "homeclaw", VoteType.YES, VoteWeight.STANDARD)
    engine.submit_vote(decision.id, "pilotclaw", VoteType.YES, VoteWeight.STANDARD)
    engine.submit_vote(decision.id, "andreas_betz", VoteType.YES, VoteWeight.OWNER)

    print(f"Entscheidung: {decision.title}")
    print(f"Status: {decision.status.value}")
    print(f"Ergebnis: {decision.result}")
    print()


def example_auto_resolution():
    """Beispiel: Auto-Resolution bei Low-Priority."""
    from datetime import datetime, timezone, timedelta

    engine = ConsensusEngine(log_dir=Path("./decision_logs"))

    decision = engine.create_decision(
        title="Dokumentation-Farbgebung",
        description="Sollen Code-Beispiele in docs blau oder grün hinterlegt sein?",
        priority="low",
        auto_resolve_after_hours=24,
    )

    # Simuliere Zeitablauf
    decision.created_at = datetime.now(timezone.utc) - timedelta(hours=25)

    # Prüfe Auto-Resolution
    auto_resolved = engine.check_auto_resolution()

    print(f"Entscheidung: {decision.title}")
    print(f"Status: {decision.status.value}")
    print(f"Ergebnis: {decision.result}")
    print(f"Auto-resolved IDs: {auto_resolved}")
    print()


def example_veto_scenario():
    """Beispiel: Veto bei Sicherheitsbedenken."""
    engine = ConsensusEngine(log_dir=Path("./decision_logs"))

    decision = engine.create_decision(
        title="Externer API-Zugriff",
        description="Soll OpenClaw externen APIs Schreibzugriff erlauben?",
        priority="critical",
        voting_method=VotingMethod.UNANIMOUS,
    )

    engine.submit_vote(decision.id, "homeclaw", VoteType.YES, rationale="Nützlich für Integration")
    engine.submit_vote(decision.id, "orakel", VoteType.VETO, rationale="Sicherheitsrisiko zu hoch")

    print(f"Entscheidung: {decision.title}")
    print(f"Status: {decision.status.value}")
    print(f"Ergebnis: {decision.result}")
    print()


def example_audit_trail():
    """Beispiel: Audit-Trail Export."""
    engine = ConsensusEngine(log_dir=Path("./decision_logs"))

    decision = engine.create_decision(
        title="Team-Meeting-Turnus",
        description="Wöchentliches Team-Meeting einführen",
        priority="medium",
        voting_method=VotingMethod.MAJORITY,
    )

    engine.submit_vote(decision.id, "agent1", VoteType.YES, rationale="Gut für Sync")
    engine.submit_vote(decision.id, "agent2", VoteType.YES)
    engine.submit_vote(decision.id, "agent3", VoteType.NO, rationale="Zu viel Overhead")

    # Exportiere Decision-Log
    export_path = engine.export_decision_log(decision.id)
    print(f"Exportiert nach: {export_path}")

    # Zeige Audit-Trail
    history = engine.get_decision_history(limit=10)
    print(f"\nAudit-Trail ({len(history)} Einträge):")
    for log in history:
        print(f"  [{log.timestamp.strftime('%H:%M:%S')}] {log.action} by {log.agent_id}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Konsens-Engine Beispiele")
    print("=" * 60)
    print()

    example_majority_decision()
    example_unanimous_critical()
    example_weighted_owner_decision()
    example_veto_scenario()
    example_auto_resolution()
    example_audit_trail()

    print("=" * 60)
    print("Alle Beispiele durchgelaufen")
    print("=" * 60)
