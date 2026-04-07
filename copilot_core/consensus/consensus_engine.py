"""
Konsens-Engine für Agenten-Entscheidungen

Entscheidungs-Framework für strittige Fragen mit:
- Voting-Mechanismen (Weighted, Unanimous, Majority)
- Decision-Logging für Audit-Trail
- Auto-Resolution für Low-Priority-Entscheidungen
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class VoteType(Enum):
    """Art des Votings für eine Entscheidung."""

    YES = auto()
    NO = auto()
    ABSTAIN = auto()
    VETO = auto()  # Nur bei Unanimous relevant


class VoteWeight(Enum):
    """Gewichtung der Stimmen je nach Agenten-Rolle."""

    STANDARD = 1
    EXPERT = 2
    LEAD = 3
    OWNER = 5  # Andreas Betz hat letztes Wort


class DecisionStatus(Enum):
    """Status einer Entscheidung."""

    PENDING = "pending"
    IN_VOTING = "in_voting"
    RESOLVED = "resolved"
    AUTO_RESOLVED = "auto_resolved"
    VETOED = "vetoed"
    EXPIRED = "expired"


class VotingMethod(Enum):
    """Verfügbare Voting-Methoden."""

    MAJORITY = "majority"  # Einfache Mehrheit (>50%)
    SUPER_MAJORITY = "super_majority"  # 2/3 Mehrheit
    UNANIMOUS = "unanimous"  # Einstimmig erforderlich
    WEIGHTED = "weighted"  # Nach Gewichtete Stimmen


@dataclass
class Vote:
    """Eine einzelne Stimme eines Agenten."""

    agent_id: str
    vote_type: VoteType
    weight: VoteWeight = VoteWeight.STANDARD
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rationale: Optional[str] = None

    @property
    def weighted_value(self) -> int:
        """Berechne gewichteten Stimmmwert."""
        if self.vote_type == VoteType.YES:
            return self.weight.value
        elif self.vote_type == VoteType.NO:
            return -self.weight.value
        else:
            return 0


@dataclass
class Decision:
    """Eine zu treffende Entscheidung."""

    id: str
    title: str
    description: str
    priority: str  # low, medium, high, critical
    voting_method: VotingMethod
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    votes: List[Vote] = field(default_factory=list)
    participants: Set[str] = field(default_factory=set)
    required_participants: Set[str] = field(default_factory=set)
    result: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    auto_resolve_after_hours: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.votes, list):
            self.votes = self.votes
        if isinstance(self.participants, set):
            self.participants = self.participants
        if isinstance(self.required_participants, set):
            self.required_participants = self.required_participants

    @property
    def is_resolved(self) -> bool:
        """Prüfe ob Entscheidung abgeschlossen."""
        return self.status in {
            DecisionStatus.RESOLVED,
            DecisionStatus.AUTO_RESOLVED,
            DecisionStatus.VETOED,
            DecisionStatus.EXPIRED,
        }

    def get_decision_hash(self) -> str:
        """Erstelle eindeutigen Hash für diese Entscheidung."""
        content = f"{self.id}:{self.title}:{self.description}:{self.created_at}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class DecisionLog:
    """Audit-Trail Eintrag für eine Entscheidung."""

    decision_id: str
    action: str
    agent_id: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None


class ConsensusEngine:
    """
    Haupt-Engine für Konsens-Entscheidungen im Agenten-Team.

    Unterstützt:
    - Mehrere Voting-Methoden (Majority, Super-Majority, Unanimous, Weighted)
    - Automatische Auflösung bei Low-Priority Entscheidungen
    - Vollständiger Audit-Trail
    - Commit-Integration für Entscheidungs-Protokolle
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        auto_commit: bool = False,
        git_repo: Optional[Path] = None,
    ):
        """
        Initialisiere die Konsens-Engine.

        Args:
            log_dir: Verzeichnis für Decision-Logs (default: ./decision_logs)
            auto_commit: Automatische Commits bei Entscheidungen
            git_repo: Pfad zum Git-Repository für Commits
        """
        self.log_dir = log_dir or Path("./decision_logs")
        self.auto_commit = auto_commit
        self.git_repo = git_repo
        self.decisions: Dict[str, Decision] = {}
        self.logs: List[DecisionLog] = []
        self._veto_callbacks: List[Callable[[Decision], None]] = []
        self._resolve_callbacks: List[Callable[[Decision], None]] = []

        # Stelle sicher, dass Log-Verzeichnis existiert
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def create_decision(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        voting_method: VotingMethod = VotingMethod.MAJORITY,
        required_participants: Optional[List[str]] = None,
        auto_resolve_after_hours: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        Erstelle eine neue Entscheidung.

        Args:
            title: Kurzer Titel der Entscheidung
            description: Detaillierte Beschreibung
            priority: Priorität (low, medium, high, critical)
            voting_method: Methode für das Voting
            required_participants: Liste von Agenten-IDs die abstimmen müssen
            auto_resolve_after_hours: Stunden nach denen Low-Priority auto-auflöst
            metadata: Zusätzliche Metadaten
            context: Kontext-Informationen für die Entscheidung

        Returns:
            Decision: Die erstellte Entscheidung
        """
        decision_id = self._generate_decision_id(title)
        decision = Decision(
            id=decision_id,
            title=title,
            description=description,
            priority=priority,
            voting_method=voting_method,
            required_participants=set(required_participants or []),
            auto_resolve_after_hours=auto_resolve_after_hours,
            metadata=metadata or {},
            context=context or {},
        )

        self.decisions[decision_id] = decision
        self._log_action(
            decision_id=decision_id,
            action="created",
            agent_id="system",
            details={
                "title": title,
                "priority": priority,
                "voting_method": voting_method.value,
            },
        )

        logger.info(f"Decision created: {decision_id} - {title}")
        return decision

    def submit_vote(
        self,
        decision_id: str,
        agent_id: str,
        vote_type: VoteType,
        weight: VoteWeight = VoteWeight.STANDARD,
        rationale: Optional[str] = None,
    ) -> bool:
        """
        Reiche eine Stimme für eine Entscheidung ein.

        Args:
            decision_id: ID der Entscheidung
            agent_id: ID des abstimmenden Agenten
            vote_type: Art der Stimme (YES, NO, ABSTAIN, VETO)
            weight: Gewichtung der Stimme
            rationale: Begründung für die Stimme

        Returns:
            bool: True wenn Stimme akzeptiert wurde
        """
        if decision_id not in self.decisions:
            logger.error(f"Decision {decision_id} not found")
            return False

        decision = self.decisions[decision_id]

        if decision.is_resolved:
            logger.warning(f"Decision {decision_id} already resolved")
            return False

        # Prüfe VETO bei Unanimous
        if vote_type == VoteType.VETO:
            if decision.voting_method == VotingMethod.UNANIMOUS:
                decision.status = DecisionStatus.VETOED
                decision.resolved_at = datetime.now(timezone.utc)
                decision.result = f"Veto by {agent_id}"
                self._log_action(
                    decision_id=decision_id,
                    action="vetoed",
                    agent_id=agent_id,
                    details={"rationale": rationale},
                    new_state={"status": "vetoed", "result": decision.result},
                )
                self._trigger_veto_callbacks(decision)
                logger.warning(f"Decision {decision_id} vetoed by {agent_id}")
                return True
            else:
                logger.warning(f"Veto not applicable for {decision.voting_method}")
                vote_type = VoteType.NO

        # Entferne alte Stimme dieses Agenten falls vorhanden
        decision.votes = [v for v in decision.votes if v.agent_id != agent_id]

        # Status auf IN_VOTING setzen wenn erste Stimme
        if len(decision.votes) == 0 and decision.status == DecisionStatus.PENDING:
            decision.status = DecisionStatus.IN_VOTING

        # Füge neue Stimme hinzu
        vote = Vote(
            agent_id=agent_id,
            vote_type=vote_type,
            weight=weight,
            rationale=rationale,
        )
        decision.votes.append(vote)
        decision.participants.add(agent_id)

        self._log_action(
            decision_id=decision_id,
            action="vote_submitted",
            agent_id=agent_id,
            details={
                "vote_type": vote_type.name,
                "weight": weight.name,
                "rationale": rationale,
            },
        )

        # Prüfe ob Entscheidung aufgelöst werden kann
        self._check_resolution(decision)

        return True

    def _check_resolution(self, decision: Decision) -> None:
        """Prüfe ob eine Entscheidung aufgelöst werden kann."""
        if decision.voting_method == VotingMethod.UNANIMOUS:
            self._check_unanimous(decision)
        elif decision.voting_method == VotingMethod.WEIGHTED:
            self._check_weighted(decision)
        elif decision.voting_method == VotingMethod.SUPER_MAJORITY:
            self._check_super_majority(decision)
        else:
            self._check_majority(decision)

    def _check_majority(self, decision: Decision) -> None:
        """Prüfe einfache Mehrheit (>50%)."""
        if not decision.votes:
            return

        # Alle erforderlichen Teilnehmer müssen abgestimmt haben
        if decision.required_participants:
            if not decision.required_participants.issubset(decision.participants):
                return

        yes_votes = sum(1 for v in decision.votes if v.vote_type == VoteType.YES)
        no_votes = sum(1 for v in decision.votes if v.vote_type == VoteType.NO)
        total_votes = yes_votes + no_votes

        if total_votes == 0:
            return

        # Mindestens 2 Stimmen erforderlich für Mehrheit
        if len(decision.votes) < 2 and not decision.required_participants:
            return

        if yes_votes > total_votes / 2:
            decision.status = DecisionStatus.RESOLVED
            decision.resolved_at = datetime.now(timezone.utc)
            decision.result = f"Approved by majority ({yes_votes}/{total_votes})"
            self._finalize_decision(decision)

    def _check_super_majority(self, decision: Decision) -> None:
        """Prüfe 2/3 Mehrheit."""
        if not decision.votes:
            return

        if decision.required_participants:
            if not decision.required_participants.issubset(decision.participants):
                return

        yes_votes = sum(1 for v in decision.votes if v.vote_type == VoteType.YES)
        no_votes = sum(1 for v in decision.votes if v.vote_type == VoteType.NO)
        total_votes = yes_votes + no_votes

        if total_votes == 0:
            return

        if yes_votes >= (total_votes * 2 / 3):
            decision.status = DecisionStatus.RESOLVED
            decision.resolved_at = datetime.now(timezone.utc)
            decision.result = f"Approved by super-majority ({yes_votes}/{total_votes})"
            self._finalize_decision(decision)

    def _check_unanimous(self, decision: Decision) -> None:
        """Prüfe Einstimmigkeit."""
        if not decision.votes:
            return

        # Bei required_participants müssen alle abgestimmt haben
        if decision.required_participants:
            if not decision.required_participants.issubset(decision.participants):
                return
            # Prüfe nur required_participants Stimmen
            relevant_votes = [v for v in decision.votes if v.agent_id in decision.required_participants]
        else:
            # Ohne required_participants: warte auf mindestens 2 Stimmen
            if len(decision.votes) < 2:
                return
            relevant_votes = decision.votes

        # Prüfe ob alle Teilnehmer YES oder ABSTAIN gewählt haben (kein VETO/NO)
        for vote in relevant_votes:
            if vote.vote_type == VoteType.NO:
                return  # Noch nicht einstimmig

        # Alle sind YES oder ABSTAIN
        yes_votes = sum(1 for v in relevant_votes if v.vote_type == VoteType.YES)
        abstain_votes = sum(1 for v in relevant_votes if v.vote_type == VoteType.ABSTAIN)

        decision.status = DecisionStatus.RESOLVED
        decision.resolved_at = datetime.now(timezone.utc)
        decision.result = f"Unanimous approval ({yes_votes} yes, {abstain_votes} abstain)"
        self._finalize_decision(decision)

    def _check_weighted(self, decision: Decision) -> None:
        """Prüfe gewichtete Stimmen."""
        if not decision.votes:
            return

        if decision.required_participants:
            if not decision.required_participants.issubset(decision.participants):
                return

        total_weight = sum(v.weighted_value for v in decision.votes)

        if total_weight > 0:
            decision.status = DecisionStatus.RESOLVED
            decision.resolved_at = datetime.now(timezone.utc)
            decision.result = f"Approved by weighted vote (net: {total_weight})"
            self._finalize_decision(decision)
        elif total_weight < 0:
            decision.status = DecisionStatus.RESOLVED
            decision.resolved_at = datetime.now(timezone.utc)
            decision.result = f"Rejected by weighted vote (net: {total_weight})"
            self._finalize_decision(decision)

    def _finalize_decision(self, decision: Decision) -> None:
        """Schließe eine Entscheidung ab und logge sie."""
        self._log_action(
            decision_id=decision.id,
            action="resolved",
            agent_id="system",
            details={"result": decision.result},
            new_state={
                "status": decision.status.value,
                "result": decision.result,
                "resolved_at": decision.resolved_at.isoformat() if decision.resolved_at else None,
            },
        )

        self._trigger_resolve_callbacks(decision)
        logger.info(f"Decision {decision.id} resolved: {decision.result}")

        if self.auto_commit:
            self._commit_decision(decision)

    def check_auto_resolution(self) -> List[str]:
        """
        Prüfe alle ausstehenden Entscheidungen auf Auto-Resolution.

        Returns:
            List[str]: Liste der auto-aufgelösten Decision-IDs
        """
        auto_resolved = []
        now = datetime.now(timezone.utc)

        for decision_id, decision in self.decisions.items():
            if decision.is_resolved:
                continue

            if decision.priority != "low":
                continue

            if decision.auto_resolve_after_hours is None:
                continue

            hours_elapsed = (now - decision.created_at).total_seconds() / 3600

            if hours_elapsed >= decision.auto_resolve_after_hours:
                decision.status = DecisionStatus.AUTO_RESOLVED
                decision.resolved_at = now
                decision.result = "Auto-resolved (low priority timeout)"

                self._log_action(
                    decision_id=decision_id,
                    action="auto_resolved",
                    agent_id="system",
                    details={
                        "reason": "low_priority_timeout",
                        "hours_elapsed": hours_elapsed,
                    },
                    new_state={"status": "auto_resolved", "result": decision.result},
                )

                auto_resolved.append(decision_id)
                logger.info(f"Decision {decision_id} auto-resolved after {hours_elapsed:.1f}h")

        return auto_resolved

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Hole eine Entscheidung nach ID."""
        return self.decisions.get(decision_id)

    def get_pending_decisions(self) -> List[Decision]:
        """Hole alle ausstehenden Entscheidungen."""
        return [d for d in self.decisions.values() if not d.is_resolved]

    def get_decision_history(self, limit: int = 100) -> List[DecisionLog]:
        """Hole Decision-Historie aus Audit-Trail."""
        return self.logs[-limit:]

    def export_decision_log(self, decision_id: str) -> Optional[Path]:
        """
        Exportiere Decision-Log als JSON-Datei.

        Returns:
            Path: Pfad zur exportierten Datei
        """
        if decision_id not in self.decisions:
            return None

        decision = self.decisions[decision_id]
        decision_logs = [
            log for log in self.logs if log.decision_id == decision_id
        ]

        export_data = {
            "decision": {
                "id": decision.id,
                "title": decision.title,
                "description": decision.description,
                "priority": decision.priority,
                "voting_method": decision.voting_method.value,
                "status": decision.status.value,
                "created_at": decision.created_at.isoformat(),
                "resolved_at": decision.resolved_at.isoformat() if decision.resolved_at else None,
                "result": decision.result,
                "votes": [
                    {
                        "agent_id": v.agent_id,
                        "vote_type": v.vote_type.name,
                        "weight": v.weight.name,
                        "timestamp": v.timestamp.isoformat(),
                        "rationale": v.rationale,
                    }
                    for v in decision.votes
                ],
                "participants": list(decision.participants),
                "metadata": decision.metadata,
            },
            "audit_trail": [
                {
                    "action": log.action,
                    "agent_id": log.agent_id,
                    "timestamp": log.timestamp.isoformat(),
                    "details": log.details,
                }
                for log in decision_logs
            ],
        }

        export_path = self.log_dir / f"decision_{decision.id}.json"
        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported decision log to {export_path}")
        return export_path

    def on_veto(self, callback: Callable[[Decision], None]) -> None:
        """Registriere Callback für Veto-Events."""
        self._veto_callbacks.append(callback)

    def on_resolve(self, callback: Callable[[Decision], None]) -> None:
        """Registriere Callback für Resolution-Events."""
        self._resolve_callbacks.append(callback)

    def _trigger_veto_callbacks(self, decision: Decision) -> None:
        """Trigger alle Veto-Callbacks."""
        for callback in self._veto_callbacks:
            try:
                callback(decision)
            except Exception as e:
                logger.error(f"Veto callback failed: {e}")

    def _trigger_resolve_callbacks(self, decision: Decision) -> None:
        """Trigger alle Resolve-Callbacks."""
        for callback in self._resolve_callbacks:
            try:
                callback(decision)
            except Exception as e:
                logger.error(f"Resolve callback failed: {e}")

    def _log_action(
        self,
        decision_id: str,
        action: str,
        agent_id: str,
        details: Optional[Dict[str, Any]] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Logge eine Aktion im Audit-Trail."""
        log_entry = DecisionLog(
            decision_id=decision_id,
            action=action,
            agent_id=agent_id,
            timestamp=datetime.now(timezone.utc),
            details=details or {},
            previous_state=previous_state,
            new_state=new_state,
        )
        self.logs.append(log_entry)

    def _generate_decision_id(self, title: str) -> str:
        """Generiere eindeutige Decision-ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        title_hash = hashlib.sha256(title.encode()).hexdigest()[:8]
        return f"DEC-{timestamp}-{title_hash}"

    def _commit_decision(self, decision: Decision) -> None:
        """Commite Entscheidung ins Git-Repository (falls konfiguriert)."""
        if not self.git_repo or not self.auto_commit:
            return

        try:
            import subprocess

            # Exportiere Decision-Log
            export_path = self.export_decision_log(decision.id)
            if not export_path:
                return

            # Git add und commit
            subprocess.run(
                ["git", "add", str(export_path)],
                cwd=self.git_repo,
                check=True,
                capture_output=True,
            )

            commit_msg = f"Decision {decision.id}: {decision.result}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.git_repo,
                check=True,
                capture_output=True,
            )

            logger.info(f"Committed decision {decision.id} to {self.git_repo}")

        except Exception as e:
            logger.error(f"Failed to commit decision {decision.id}: {e}")
